package main

import (
	"context"
	"log"
	"os"
	"path/filepath"
	"sort"

	"github.com/jackc/pgx/v5"
	"github.com/joho/godotenv"
)

func main() {
	// Try loading .env, but don't fail if missing (CI environment)
	_ = godotenv.Load("../.env")
	_ = godotenv.Load(".env")

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL not set")
	}

	conn, err := pgx.Connect(context.Background(), dbURL)
	if err != nil {
		log.Fatalf("Unable to connect to database: %v", err)
	}
	defer conn.Close(context.Background())

	// Create schema_migrations table
	_, err = conn.Exec(context.Background(), `
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version TEXT PRIMARY KEY,
			applied_at TIMESTAMPTZ DEFAULT NOW()
		);
	`)
	if err != nil {
		log.Fatalf("Failed to create schema_migrations table: %v", err)
	}

	// Read migration files
	files, err := filepath.Glob("../database/migrations/*.sql")
	if err != nil {
		log.Fatalf("Failed to find migration files: %v", err)
	}
	sort.Strings(files)

	for _, file := range files {
		version := filepath.Base(file)

		// Check if applied
		var exists bool
		err := conn.QueryRow(context.Background(), "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version=$1)", version).Scan(&exists)
		if err != nil {
			log.Fatalf("Failed to check migration status: %v", err)
		}

		if exists {
			log.Printf("Skipping %s (already applied)", version)
			continue
		}

		log.Printf("Applying %s...", version)
		content, err := os.ReadFile(file)
		if err != nil {
			log.Fatalf("Failed to read migration file: %v", err)
		}

		// Transaction
		tx, err := conn.Begin(context.Background())
		if err != nil {
			log.Fatalf("Failed to begin transaction: %v", err)
		}

		if _, err := tx.Exec(context.Background(), string(content)); err != nil {
			tx.Rollback(context.Background())
			log.Fatalf("Failed to execute migration %s: %v", version, err)
		}

		if _, err := tx.Exec(context.Background(), "INSERT INTO schema_migrations (version) VALUES ($1)", version); err != nil {
			tx.Rollback(context.Background())
			log.Fatalf("Failed to record migration %s: %v", version, err)
		}

		if err := tx.Commit(context.Background()); err != nil {
			log.Fatalf("Failed to commit transaction: %v", err)
		}
		log.Printf("Applied %s", version)
	}

	log.Println("All migrations completed.")
}
