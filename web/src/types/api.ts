// Constants
export const DEFAULT_CONVERSATION_TITLE = 'New Conversation';

// User types
export interface User {
  id: string;
  email: string;
  name: string;
  picture: string | null;
}

// Conversation types
export interface Conversation {
  id: string;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

// Message types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  files?: FileMetadata[];
  created_at: string;
}

// File types
export interface FileMetadata {
  name: string;
  type: string;
  messageId?: string;
  fileIndex?: number;
  previewUrl?: string; // blob URL for immediate display (local uploads only)
}

export interface FileUpload {
  name: string;
  type: string;
  data: string; // base64
  previewUrl?: string; // blob URL for local preview
}

// Model types
export interface Model {
  id: string;
  name: string;
}

// Upload config
export interface UploadConfig {
  maxFileSize: number;
  maxFilesPerMessage: number;
  allowedFileTypes: string[];
}

// Streaming response events
export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'done'; id: string; created_at: string }
  | { type: 'error'; message: string };

// API response types
export interface AuthResponse {
  token: string;
  user: User;
}

export interface ConversationsResponse {
  conversations: Conversation[];
}

export interface ModelsResponse {
  models: Model[];
  default: string;
}

export interface ChatResponse {
  id: string;
  role: 'assistant';
  content: string;
  created_at: string;
}

export interface ErrorResponse {
  error: string;
}

export interface VersionResponse {
  version: string | null;
}