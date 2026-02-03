// P2P Swarm Gateway - Cloud Bridge Super-Node
//
// This Go service acts as a "super-node" that bridges the simulated
// P2P swarm network with external systems. It provides REST APIs
// for injecting messages and querying network status.
package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

var (
	port     string
	logLevel string
)

func init() {
	flag.StringVar(&port, "port", getEnv("PORT", "8080"), "Server port")
	flag.StringVar(&logLevel, "log-level", getEnv("LOG_LEVEL", "info"), "Log level")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func main() {
	flag.Parse()

	// Initialize storage
	storage := NewStorage()

	// Initialize router
	router := NewRouter(storage)

	// Create server
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Printf("🚀 P2P Swarm Gateway starting on port %s", port)
		log.Printf("📡 Endpoints:")
		log.Printf("   POST /inject    - Inject message into swarm")
		log.Printf("   GET  /status    - Get gateway status")
		log.Printf("   GET  /messages  - Get stored messages")
		log.Printf("   GET  /health    - Health check")
		
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server stopped")
}
