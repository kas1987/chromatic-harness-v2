export interface PrismEvent {
  id: string;
  source: 'gmail' | 'gcal' | 'slack' | 'discord' | 'linear' | 'github' | 'substack';
  received_at: string;
  subject: string;
  body_text: string;
  sender?: string;
  thread_id?: string;
  url?: string;
  metadata: Record<string, unknown>;
}
