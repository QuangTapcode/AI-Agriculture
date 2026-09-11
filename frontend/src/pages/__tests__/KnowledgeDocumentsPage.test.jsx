import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getKnowledgeDocuments = vi.fn();

vi.mock('../../services/aiApi', () => ({
  aiApi: { getKnowledgeDocuments: (...a) => getKnowledgeDocuments(...a) },
}));

import KnowledgeDocumentsPage from '../KnowledgeDocumentsPage';

const renderPage = () =>
  render(
    <MemoryRouter>
      <KnowledgeDocumentsPage />
    </MemoryRouter>
  );

describe('knowledge catalogue resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('survives a catalogue response that omits the document list', async () => {
    getKnowledgeDocuments.mockResolvedValue({ summary: {} });

    renderPage();

    // Loader debounce 250ms: phải chờ phản hồi được áp vào state rồi mới kiểm tra,
    // nếu không ta chỉ đang xác nhận lần render đầu với state khởi tạo.
    await waitFor(() => expect(getKnowledgeDocuments).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: /Tài liệu đã nạp/i })).toBeInTheDocument()
    );
  });

  it('lists the documents the backend returned', async () => {
    getKnowledgeDocuments.mockResolvedValue({
      summary: { approved: 1 },
      documents: [{ id: 1, title: 'Quy trình bón phân', source_name: 'Cục Trồng trọt', status: 'approved' }],
    });

    renderPage();

    expect(await screen.findByText('Quy trình bón phân')).toBeInTheDocument();
  });
});
