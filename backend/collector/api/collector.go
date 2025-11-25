package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// GBFS Response Structures
type GBFSResponse struct {
	LastUpdated int64 `json:"last_updated"`
	TTL         int   `json:"ttl"`
	Data        struct {
		Stations []StationStatus `json:"stations"`
	} `json:"data"`
}

type StationStatus struct {
	StationID          string `json:"station_id"`
	NumBikesAvailable  int    `json:"num_bikes_available"`
	NumEbikesAvailable int    `json:"num_ebikes_available"`
	NumDocksAvailable  int    `json:"num_docks_available"`
	IsInstalled        int    `json:"is_installed"`
	IsRenting          int    `json:"is_renting"`
	IsReturning        int    `json:"is_returning"`
	LastReported       int64  `json:"last_reported"`
}

type GBFSInfoResponse struct {
	LastUpdated int64 `json:"last_updated"`
	Data        struct {
		Stations []StationInformation `json:"stations"`
	} `json:"data"`
}

type StationInformation struct {
	StationID string  `json:"station_id"`
	Name      string  `json:"name"`
	Lat       float64 `json:"lat"`
	Lon       float64 `json:"lon"`
	Capacity  int     `json:"capacity"`
}

const (
	GBFSStatusURL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_status.json"
	GBFSInfoURL   = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_information.json"
)

// Global DB Pool for warm starts
var dbPool *pgxpool.Pool

// Handler is the entry point for Vercel Serverless Function
func Handler(w http.ResponseWriter, r *http.Request) {
	// 1. Security Check
	cronSecret := os.Getenv("CRON_SECRET")
	if cronSecret == "" {
		http.Error(w, "CRON_SECRET is not set in environment", http.StatusInternalServerError)
		return
	}

	authHeader := r.Header.Get("Authorization")
	expectedHeader := fmt.Sprintf("Bearer %s", cronSecret)
	if authHeader != expectedHeader {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	// 2. Initialize DB Pool if needed
	if dbPool == nil {
		dbURL := os.Getenv("DATABASE_URL")
		if dbURL == "" {
			http.Error(w, "DATABASE_URL is not set", http.StatusInternalServerError)
			return
		}

		config, err := pgxpool.ParseConfig(dbURL)
		if err != nil {
			http.Error(w, fmt.Sprintf("Unable to parse DB URL: %v", err), http.StatusInternalServerError)
			return
		}

		// Configure pool settings for serverless
		config.MaxConns = 5
		config.MinConns = 0 // Allow scaling down to 0
		config.MaxConnLifetime = 30 * time.Minute

		pool, err := pgxpool.NewWithConfig(context.Background(), config)
		if err != nil {
			http.Error(w, fmt.Sprintf("Unable to connect to database: %v", err), http.StatusInternalServerError)
			return
		}
		dbPool = pool
	}

	// 3. Execute Logic
	if err := pollAndSave(context.Background(), dbPool); err != nil {
		log.Printf("Error in poll: %v", err)
		http.Error(w, fmt.Sprintf("Error: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Collector ran successfully"))
}

func pollAndSave(ctx context.Context, db *pgxpool.Pool) error {
	// 1. Fetch and Upsert Station Information (Metadata)
	if err := fetchAndUpsertStations(ctx, db); err != nil {
		log.Printf("Error fetching station info: %v", err)
	}

	// 2. Fetch Station Status
	log.Println("Fetching GBFS status data...")
	resp, err := http.Get(GBFSStatusURL)
	if err != nil {
		return fmt.Errorf("failed to fetch GBFS status: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("bad status code: %d", resp.StatusCode)
	}

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read body: %w", err)
	}

	var gbfs GBFSResponse
	if err := json.Unmarshal(bodyBytes, &gbfs); err != nil {
		return fmt.Errorf("failed to decode JSON: %w", err)
	}

	// 3. Upload to R2
	if err := uploadToR2(ctx, bodyBytes, gbfs.LastUpdated); err != nil {
		log.Printf("Warning: Failed to upload to R2: %v", err)
	}

	// 4. Fetch latest status from DB for deduplication (Optimized)
	latestStatuses, err := fetchLatestStationStatuses(ctx, db)
	if err != nil {
		log.Printf("Warning: Failed to fetch latest statuses: %v. Proceeding with full insert.", err)
		latestStatuses = make(map[string]StationStatus)
	}

	// 5. Batch insert into TimescaleDB (only changed records) AND Upsert current status
	timestamp := time.Unix(gbfs.LastUpdated, 0)
	historyBatch := &pgx.Batch{}
	currentBatch := &pgx.Batch{}
	insertCount := 0

	for _, s := range gbfs.Data.Stations {
		// Always upsert to current_station_status to keep it fresh
		currentBatch.Queue(`
			INSERT INTO current_station_status (station_id, num_bikes_available, num_ebikes_available, num_docks_available, is_installed, is_renting, is_returning, last_updated)
			VALUES ($1, $2, $3, $4, $5 = 1, $6 = 1, $7 = 1, $8)
			ON CONFLICT (station_id) DO UPDATE SET
				num_bikes_available = EXCLUDED.num_bikes_available,
				num_ebikes_available = EXCLUDED.num_ebikes_available,
				num_docks_available = EXCLUDED.num_docks_available,
				is_installed = EXCLUDED.is_installed,
				is_renting = EXCLUDED.is_renting,
				is_returning = EXCLUDED.is_returning,
				last_updated = EXCLUDED.last_updated
		`, s.StationID, s.NumBikesAvailable, s.NumEbikesAvailable, s.NumDocksAvailable, s.IsInstalled, s.IsRenting, s.IsReturning, timestamp)

		// Check if status has changed for history
		if lastStatus, ok := latestStatuses[s.StationID]; ok {
			if lastStatus.NumBikesAvailable == s.NumBikesAvailable &&
				lastStatus.NumEbikesAvailable == s.NumEbikesAvailable &&
				lastStatus.NumDocksAvailable == s.NumDocksAvailable &&
				lastStatus.IsInstalled == s.IsInstalled &&
				lastStatus.IsRenting == s.IsRenting &&
				lastStatus.IsReturning == s.IsReturning {
				continue // Skip history insert if nothing changed
			}
		}

		historyBatch.Queue(`
			INSERT INTO station_status (time, station_id, num_bikes_available, num_ebikes_available, num_docks_available, is_installed, is_renting, is_returning)
			VALUES ($1, $2, $3, $4, $5, $6 = 1, $7 = 1, $8 = 1)
		`, timestamp, s.StationID, s.NumBikesAvailable, s.NumEbikesAvailable, s.NumDocksAvailable, s.IsInstalled, s.IsRenting, s.IsReturning)
		insertCount++
	}

	// Execute Current Status Upsert
	brCurrent := db.SendBatch(ctx, currentBatch)
	if _, err := brCurrent.Exec(); err != nil {
		log.Printf("Error upserting current status: %v", err)
		// Don't fail the whole run, history is more important
	}
	brCurrent.Close()

	// Execute History Insert
	if insertCount > 0 {
		log.Printf("Inserting %d changed station statuses...", insertCount)
		brHistory := db.SendBatch(ctx, historyBatch)
		defer brHistory.Close()

		if _, err := brHistory.Exec(); err != nil {
			return fmt.Errorf("failed to execute history batch: %w", err)
		}
		log.Println("Successfully inserted history batch.")
	} else {
		log.Println("No station status changes detected. Skipping history insert.")
	}

	return nil
}

func fetchLatestStationStatuses(ctx context.Context, db *pgxpool.Pool) (map[string]StationStatus, error) {
	// Fetch the most recent status for each station from the optimized table
	rows, err := db.Query(ctx, `
		SELECT 
			station_id, 
			num_bikes_available, 
			num_ebikes_available, 
			num_docks_available, 
			CASE WHEN is_installed THEN 1 ELSE 0 END, 
			CASE WHEN is_renting THEN 1 ELSE 0 END, 
			CASE WHEN is_returning THEN 1 ELSE 0 END
		FROM current_station_status
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	statuses := make(map[string]StationStatus)
	for rows.Next() {
		var s StationStatus
		if err := rows.Scan(
			&s.StationID,
			&s.NumBikesAvailable,
			&s.NumEbikesAvailable,
			&s.NumDocksAvailable,
			&s.IsInstalled,
			&s.IsRenting,
			&s.IsReturning,
		); err != nil {
			return nil, err
		}
		statuses[s.StationID] = s
	}
	return statuses, nil
}

func fetchAndUpsertStations(ctx context.Context, db *pgxpool.Pool) error {
	log.Println("Fetching GBFS station information...")
	resp, err := http.Get(GBFSInfoURL)
	if err != nil {
		return fmt.Errorf("failed to fetch GBFS info: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("bad status code: %d", resp.StatusCode)
	}

	var gbfsInfo GBFSInfoResponse
	if err := json.NewDecoder(resp.Body).Decode(&gbfsInfo); err != nil {
		return fmt.Errorf("failed to decode JSON: %w", err)
	}

	log.Printf("Fetched %d stations metadata. Upserting...", len(gbfsInfo.Data.Stations))

	batch := &pgx.Batch{}
	for _, s := range gbfsInfo.Data.Stations {
		batch.Queue(`
			INSERT INTO stations (station_id, name, lat, lon, capacity, last_updated)
			VALUES ($1, $2, $3, $4, $5, NOW())
			ON CONFLICT (station_id) DO UPDATE SET
				name = EXCLUDED.name,
				lat = EXCLUDED.lat,
				lon = EXCLUDED.lon,
				capacity = EXCLUDED.capacity,
				last_updated = NOW()
		`, s.StationID, s.Name, s.Lat, s.Lon, s.Capacity)
	}

	br := db.SendBatch(ctx, batch)
	defer br.Close()

	if _, err := br.Exec(); err != nil {
		return fmt.Errorf("failed to execute station upsert batch: %w", err)
	}

	return nil
}

func uploadToR2(ctx context.Context, data []byte, lastUpdated int64) error {
	accountID := os.Getenv("R2_ACCOUNT_ID")
	accessKey := os.Getenv("R2_ACCESS_KEY_ID")
	secretKey := os.Getenv("R2_SECRET_ACCESS_KEY")
	bucketName := os.Getenv("R2_BUCKET_NAME")

	if accountID == "" || accessKey == "" || secretKey == "" || bucketName == "" {
		return fmt.Errorf("R2 credentials missing")
	}

	r2Endpoint := fmt.Sprintf("https://%s.r2.cloudflarestorage.com", accountID)

	cfg, err := config.LoadDefaultConfig(ctx,
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
		config.WithRegion("auto"),
	)
	if err != nil {
		return err
	}

	client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(r2Endpoint)
	})

	key := fmt.Sprintf("raw/station_status_%d.json", lastUpdated)

	_, err = client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(key),
		Body:   bytes.NewReader(data),
	})

	return err
}
