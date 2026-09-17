import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getKnowledgeDocuments = vi.fn();
const getKnowledgeStatus = vi.fn();
const getKnowledgeSourceCandidates = vi.fn();
const approveKnowledgeSourceCandidate = vi.fn();
const rejectKnowledgeSourceCandidate = vi.fn();

vi.mock('../../services/aiApi', () => ({
  aiApi: {
    getKnowledgeDocuments: (...args) => getKnowledgeDocuments(...args),
    getKnowledgeStatus: (...args) => getKnowledgeStatus(...args),
    getKnowledgeSourceCandidates: (...args) => getKnowledgeSourceCandidates(...args),
    approveKnowledgeSourceCandidate: (...args) => approveKnowledgeSourceCandidate(...args),
    rejectKnowledgeSourceCandidate: (...args) => rejectKnowledgeSourceCandidate(...args),
  },
}));

import KnowledgeDocumentsPage from '../KnowledgeDocumentsPage';

describe('knowledge source review actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getKnowledgeDocuments.mockResolvedValue({ documents: [], summary: {} });
    getKnowledgeStatus.mockResolvedValue({});
    getKnowledgeSourceCandidates.mockResolvedValue({
      candidates: [{
        id: 1002,
        name: 'Hướng dẫn trồng nho Hạ Đen',
        url: 'https://example.gov.vn/nho-ha-den',
        domain: 'example.gov.vn',
        discovered_from: 'Cổng khuyến nông',
        status: 'pending',
      }],
    });
    approveKnowledgeSourceCandidate.mockResolvedValue({
      candidate: { id: 1002, status: 'approved' },
      next_ingestion_uses_candidate: true,
    });
    rejectKnowledgeSourceCandidate.mockResolvedValue({
      candidate: { id: 1002, status: 'rejected' },
      next_ingestion_uses_candidate: false,
    });
  });

  it('shows review actions and approves a pending source', async () => {
    render(<MemoryRouter><KnowledgeDocumentsPage /></MemoryRouter>);

    expect(await screen.findByRole('button', { name: 'Duyệt nguồn' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Từ chối nguồn' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Duyệt nguồn' }));

    await waitFor(() => expect(approveKnowledgeSourceCandidate).toHaveBeenCalledWith(1002));
    expect(await screen.findByRole('status')).toHaveTextContent('Đã duyệt nguồn');
  });
});
