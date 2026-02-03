package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
)

// Message represents the standard message envelope used in the swarm
type Message struct {
	ID        string                 `json:"id"`
	From      string                 `json:"from"`
	To        *string                `json:"to,omitempty"`
	TTL       int                    `json:"ttl"`
	Seq       int                    `json:"seq"`
	Urgency   int                    `json:"urgency"`
	Payload   map[string]interface{} `json:"payload"`
	Timestamp string                 `json:"timestamp"`
}

// InjectRequest represents a request to inject a message
type InjectRequest struct {
	From    string                 `json:"from"`
	To      *string                `json:"to,omitempty"`
	TTL     int                    `json:"ttl"`
	Urgency int                    `json:"urgency"`
	Payload map[string]interface{} `json:"payload"`
}

// StatusResponse represents the gateway status
type StatusResponse struct {
	Status         string    `json:"status"`
	Uptime         string    `json:"uptime"`
	MessageCount   int       `json:"message_count"`
	LastActivity   string    `json:"last_activity"`
	Version        string    `json:"version"`
	StartTime      time.Time `json:"start_time"`
}

// MessagesResponse represents a list of messages
type MessagesResponse struct {
	Messages []Message `json:"messages"`
	Total    int       `json:"total"`
	Page     int       `json:"page"`
	PageSize int       `json:"page_size"`
}

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error   string `json:"error"`
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Router handles HTTP routing
type Router struct {
	storage   *Storage
	startTime time.Time
}

// NewRouter creates a new router instance
func NewRouter(storage *Storage) *mux.Router {
	r := &Router{
		storage:   storage,
		startTime: time.Now(),
	}

	router := mux.NewRouter()

	// API routes
	api := router.PathPrefix("/").Subrouter()
	
	api.HandleFunc("/inject", r.handleInject).Methods("POST")
	api.HandleFunc("/status", r.handleStatus).Methods("GET")
	api.HandleFunc("/messages", r.handleMessages).Methods("GET")
	api.HandleFunc("/messages/{id}", r.handleGetMessage).Methods("GET")
	api.HandleFunc("/health", r.handleHealth).Methods("GET")

	// Middleware
	router.Use(loggingMiddleware)
	router.Use(corsMiddleware)

	return router
}

// handleInject handles POST /inject - inject a message into the swarm
func (r *Router) handleInject(w http.ResponseWriter, req *http.Request) {
	var injectReq InjectRequest
	
	if err := json.NewDecoder(req.Body).Decode(&injectReq); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON", err.Error())
		return
	}

	// Create message
	msg := Message{
		ID:        uuid.New().String(),
		From:      injectReq.From,
		To:        injectReq.To,
		TTL:       injectReq.TTL,
		Seq:       r.storage.GetNextSequence(),
		Urgency:   injectReq.Urgency,
		Payload:   injectReq.Payload,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}

	// Default TTL if not specified
	if msg.TTL == 0 {
		msg.TTL = 10
	}

	// Validate urgency
	if msg.Urgency < 0 || msg.Urgency > 5 {
		msg.Urgency = 2 // Default to NORMAL
	}

	// Store message
	r.storage.AddMessage(msg)

	log.Printf("Message injected: %s from %s", msg.ID[:8], msg.From)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(msg)
}

// handleStatus handles GET /status - get gateway status
func (r *Router) handleStatus(w http.ResponseWriter, req *http.Request) {
	uptime := time.Since(r.startTime)
	
	status := StatusResponse{
		Status:       "running",
		Uptime:       uptime.String(),
		MessageCount: r.storage.GetMessageCount(),
		LastActivity: r.storage.GetLastActivity().Format(time.RFC3339),
		Version:      "1.0.0",
		StartTime:    r.startTime,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

// handleMessages handles GET /messages - get stored messages
func (r *Router) handleMessages(w http.ResponseWriter, req *http.Request) {
	// Parse pagination params
	page, _ := strconv.Atoi(req.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(req.URL.Query().Get("page_size"))
	
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	messages, total := r.storage.GetMessages(page, pageSize)

	response := MessagesResponse{
		Messages: messages,
		Total:    total,
		Page:     page,
		PageSize: pageSize,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleGetMessage handles GET /messages/{id} - get a specific message
func (r *Router) handleGetMessage(w http.ResponseWriter, req *http.Request) {
	vars := mux.Vars(req)
	id := vars["id"]

	msg, found := r.storage.GetMessage(id)
	if !found {
		writeError(w, http.StatusNotFound, "Message not found", "No message with ID: "+id)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(msg)
}

// handleHealth handles GET /health - health check endpoint
func (r *Router) handleHealth(w http.ResponseWriter, req *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

// writeError writes an error response
func writeError(w http.ResponseWriter, code int, error string, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(ErrorResponse{
		Error:   error,
		Code:    code,
		Message: message,
	})
}

// loggingMiddleware logs HTTP requests
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %v", r.Method, r.RequestURI, time.Since(start))
	})
}

// corsMiddleware adds CORS headers
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
