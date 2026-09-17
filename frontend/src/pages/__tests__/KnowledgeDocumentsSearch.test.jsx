import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getKnowledgeDocuments = vi.fn();
const getKnowledgeStatus = vi.fn();
const getKnowledgeSourceCandidates = vi.fn();
const startKnowledgeDiscovery = vi.fn();

vi.mock('../../services/aiApi', () => ({
  aiApi: {
    getKnowledgeDocuments: (...args) => getKnowledgeDocuments(...args),
    getKnowledgeStatus: (...args) => getKnowledgeStatus(...args),
    getKnowledgeSourceCandidates: (...args) => getKnowledgeSourceCandidates(...args),
    startKnowledgeDiscovery: (...args) => startKnowledgeDiscovery(...args),
  },
}));

import KnowledgeDocumentsPage from '../KnowledgeDocumentsPage';

describe('knowledge discovery search panel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getKnowledgeDocuments.mockResolvedValue({ summary: {}, documents: [] });
    getKnowledgeSourceCandidates.mockResolvedValue({ candidates: [] });
    getKnowledgeStatus.mockResolvedValue({
      latest_query_discovery: {
        job_id: 7,
        status: 'indexed',
        question: 'Kỹ thuật trồng nho ngón tay tại Đà Nẵng',
        keywords: ['nho ngón tay', 'Đà Nẵng'],
        verification_status: 'passed',
        apply_status: 'applied',
        documents_indexed: 1,
      },
    });
    startKnowledgeDiscovery.mockResolvedValue({
      job_id: 8,
      status: 'indexed',
      question: 'Kỹ thuật trồng nho ngón tay tại Đà Nẵng',
      keywords: ['nho ngón tay', 'Đà Nẵng'],
      verification_status: 'passed',
      apply_status: 'applied',
      documents_indexed: 1,
    });
  });

  it('shows extracted topics and starts an immediate discovery search', async () => {
    render(<MemoryRouter><KnowledgeDocumentsPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Cần tìm' })).toBeInTheDocument();
    expect(await screen.findByText('nho ngón tay')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }));

    await waitFor(() => expect(startKnowledgeDiscovery).toHaveBeenCalledWith({
      question: 'Kỹ thuật trồng nho ngón tay tại Đà Nẵng',
    }));
    expect(await screen.findByText('Đã kiểm tra đạt và đã áp dụng vào kho chính')).toBeInTheDocument();
  });

  it('shows the source name and the stored reason when a document is rejected', async () => {
    getKnowledgeDocuments.mockResolvedValue({
      summary: {},
      documents: [{
        id: 91,
        title: 'Tài liệu kiểm tra chất lượng',
        source_name: 'Cổng khuyến nông Đà Nẵng',
        source_url: 'https://khuyen-nong.example/rejected',
        status: 'rejected',
        indexed: false,
        chunks: null,
        rejection_reason: 'Nội dung chưa đạt độ dài tối thiểu',
        quality_checks: ['Nội dung chưa đạt độ dài tối thiểu'],
      }],
    });

    render(<MemoryRouter><KnowledgeDocumentsPage /></MemoryRouter>);

    expect(await screen.findByText('Nguồn:')).toBeInTheDocument();
    expect(await screen.findByText('Cổng khuyến nông Đà Nẵng')).toBeInTheDocument();
    expect(await screen.findByText('Lý do không được áp dụng')).toBeInTheDocument();
    expect(await screen.findByText('Nội dung chưa đạt độ dài tối thiểu')).toBeInTheDocument();
  });
});
