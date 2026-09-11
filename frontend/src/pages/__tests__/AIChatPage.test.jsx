import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getConversations = vi.fn();
const getDocuments = vi.fn();
const getKnowledgeStatus = vi.fn();

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, user: { id: 1, name: 'Nông hộ thử nghiệm' } }),
}));

vi.mock('../../services/aiApi', () => ({
  aiApi: {
    getConversations: (...a) => getConversations(...a),
    getDocuments: (...a) => getDocuments(...a),
    getKnowledgeStatus: (...a) => getKnowledgeStatus(...a),
    getConversation: vi.fn(),
    ask: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    deleteConversation: vi.fn(),
    deleteAllConversations: vi.fn(),
  },
}));

import AIChatPage from '../AIChatPage';

describe('AI assistant resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDocuments.mockResolvedValue({});
    getKnowledgeStatus.mockResolvedValue(null);
  });

  it('survives a conversation list response that omits the history array', async () => {
    getConversations.mockResolvedValue({ has_more: false });

    render(
      <MemoryRouter>
        <AIChatPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(getConversations).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: /Trợ lý nông nghiệp/i })).toBeInTheDocument()
    );
  });

  it('lists the conversations the backend returned', async () => {
    getConversations.mockResolvedValue({
      history: [
        {
          id: 'abc',
          user_message: 'Sâu bệnh trên lúa',
          ai_response: 'Kiểm tra rầy nâu ở gốc.',
          turn_count: 2,
          created_at: '2026-09-01T00:00:00Z',
        },
      ],
      has_more: false,
    });

    render(
      <MemoryRouter>
        <AIChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('Sâu bệnh trên lúa')).toBeInTheDocument();
  });
});
