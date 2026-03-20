export interface PartialTranscript {
  text: string;
  start_time: number;
  end_time: number;
  is_final?: boolean;
}

export interface OutlineTopic {
  topic_name: string;
  description: string;
}

export interface CompletionOutline {
  topics: OutlineTopic[];
}

export interface ASRWebSocketMessage {
  type: 'transcript' | 'outline' | 'session_message' | 'error';
  text?: string;
  start_time?: number;
  end_time?: number;
  is_final?: boolean;
  topics?: OutlineTopic[];
  ai_response?: {
    message: string;
    implicit_gaps: Array<{ gap_description: string; suggested_question: string }>;
    current_round: number;
    max_rounds: number;
  };
  error_code?: string;
  error_message?: string;
}
