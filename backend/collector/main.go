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

	// Load .env is not needed on Vercel as env vars are injected,
	// but for local 'vercel dev' it might be needed if not using vercel env pull.
	// We'll assume env vars are present.

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		http.Error(w, "DATABASE_URL is not set", http.StatusInternalServerError)
		return
	}

	// Connect to DB (Create a new connection per invocation for simplicity,
	// though global pool is better for warm starts. For Cron every 1m, this is fine)
	config, err := pgxpool.ParseConfig(dbURL)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to parse DB URL: %v", err), http.StatusInternalServerError)
		return
	}
	pool, err := pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to connect to database: %v", err), http.StatusInternalServerError)
		return
	}
	defer pool.Close()

	if err := pollAndSave(context.Background(), pool); err != nil {
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

	log.Printf("Fetched %d station statuses. Inserting...", len(gbfs.Data.Stations))

	// 3. Upload to R2
	if err := uploadToR2(ctx, bodyBytes, gbfs.LastUpdated); err != nil {
		log.Printf("Warning: Failed to upload to R2: %v", err)
	}

	// 4. Batch insert into TimescaleDB
	timestamp := time.Unix(gbfs.LastUpdated, 0)
	batch := &pgx.Batch{}

	for _, s := range gbfs.Data.Stations {
		batch.Queue(`
			INSERT INTO station_status (time, station_id, num_bikes_available, num_ebikes_available, num_docks_available, is_installed, is_renting, is_returning)
			VALUES ($1, $2, $3, $4, $5, $6 = 1, $7 = 1, $8 = 1)
		`, timestamp, s.StationID, s.NumBikesAvailable, s.NumEbikesAvailable, s.NumDocksAvailable, s.IsInstalled, s.IsRenting, s.IsReturning)
	}

	br := db.SendBatch(ctx, batch)
	defer br.Close()

	if _, err := br.Exec(); err != nil {
		return fmt.Errorf("failed to execute batch: %w", err)
	}

	log.Println("Successfully inserted batch.")
	return nil
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
