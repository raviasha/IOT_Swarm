package main

import (
	"sync"
	"time"
)

// Storage provides thread-safe message storage
type Storage struct {
	mu           sync.RWMutex
	messages     []Message
	messageIndex map[string]int
	sequence     int
	lastActivity time.Time
	maxMessages  int
}

// NewStorage creates a new storage instance
func NewStorage() *Storage {
	return &Storage{
		messages:     make([]Message, 0),
		messageIndex: make(map[string]int),
		sequence:     0,
		lastActivity: time.Now(),
		maxMessages:  10000, // Maximum messages to store
	}
}

// AddMessage adds a message to storage
func (s *Storage) AddMessage(msg Message) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Check if we need to remove old messages
	if len(s.messages) >= s.maxMessages {
		// Remove oldest 10%
		removeCount := s.maxMessages / 10
		s.messages = s.messages[removeCount:]
		
		// Rebuild index
		s.messageIndex = make(map[string]int)
		for i, m := range s.messages {
			s.messageIndex[m.ID] = i
		}
	}

	// Add new message
	s.messageIndex[msg.ID] = len(s.messages)
	s.messages = append(s.messages, msg)
	s.lastActivity = time.Now()
}

// GetMessage retrieves a message by ID
func (s *Storage) GetMessage(id string) (Message, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	idx, found := s.messageIndex[id]
	if !found {
		return Message{}, false
	}

	return s.messages[idx], true
}

// GetMessages retrieves messages with pagination
func (s *Storage) GetMessages(page, pageSize int) ([]Message, int) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	total := len(s.messages)
	
	// Calculate offset
	offset := (page - 1) * pageSize
	if offset >= total {
		return []Message{}, total
	}

	// Calculate end
	end := offset + pageSize
	if end > total {
		end = total
	}

	// Return slice (reversed so newest first)
	result := make([]Message, end-offset)
	for i := 0; i < end-offset; i++ {
		result[i] = s.messages[total-1-offset-i]
	}

	return result, total
}

// GetMessageCount returns the total number of stored messages
func (s *Storage) GetMessageCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.messages)
}

// GetNextSequence returns the next sequence number
func (s *Storage) GetNextSequence() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.sequence++
	return s.sequence
}

// GetLastActivity returns the timestamp of the last activity
func (s *Storage) GetLastActivity() time.Time {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastActivity
}

// Clear removes all messages from storage
func (s *Storage) Clear() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.messages = make([]Message, 0)
	s.messageIndex = make(map[string]int)
	s.lastActivity = time.Now()
}

// GetMessagesByFrom retrieves messages from a specific sender
func (s *Storage) GetMessagesByFrom(from string, limit int) []Message {
	s.mu.RLock()
	defer s.mu.RUnlock()

	result := make([]Message, 0)
	for i := len(s.messages) - 1; i >= 0 && len(result) < limit; i-- {
		if s.messages[i].From == from {
			result = append(result, s.messages[i])
		}
	}
	return result
}

// GetMessagesWithinTimeRange retrieves messages within a time range
func (s *Storage) GetMessagesWithinTimeRange(start, end time.Time, limit int) []Message {
	s.mu.RLock()
	defer s.mu.RUnlock()

	result := make([]Message, 0)
	for i := len(s.messages) - 1; i >= 0 && len(result) < limit; i-- {
		msgTime, err := time.Parse(time.RFC3339, s.messages[i].Timestamp)
		if err != nil {
			continue
		}
		if msgTime.After(start) && msgTime.Before(end) {
			result = append(result, s.messages[i])
		}
	}
	return result
}

// Statistics returns storage statistics
func (s *Storage) Statistics() map[string]interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Count by urgency
	urgencyCounts := make(map[int]int)
	for _, msg := range s.messages {
		urgencyCounts[msg.Urgency]++
	}

	// Count unique senders
	senders := make(map[string]bool)
	for _, msg := range s.messages {
		senders[msg.From] = true
	}

	return map[string]interface{}{
		"total_messages":  len(s.messages),
		"unique_senders":  len(senders),
		"sequence":        s.sequence,
		"max_capacity":    s.maxMessages,
		"urgency_counts":  urgencyCounts,
		"last_activity":   s.lastActivity,
	}
}
