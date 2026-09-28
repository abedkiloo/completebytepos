import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import BlogPosts from './BlogPosts';
import { cmsAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  cmsAPI: {
    listPosts: jest.fn(),
    createPost: jest.fn(),
    updatePost: jest.fn(),
    deletePost: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (v) => v,
}));

const POSTS = [
  { id: 1, title: 'Sofa stand guide', slug: 'sofa-stand-guide', status: 'published', published_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-02T10:00:00Z' },
  { id: 2, title: 'Webbing tips', slug: 'webbing-tips', status: 'draft', published_at: null, updated_at: '2026-09-03T10:00:00Z' },
];

describe('BlogPosts', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cmsAPI.listPosts.mockResolvedValue({ data: { results: POSTS } });
    cmsAPI.updatePost.mockResolvedValue({ data: {} });
    cmsAPI.createPost.mockResolvedValue({ data: { id: 3 } });
    cmsAPI.deletePost.mockResolvedValue({});
  });

  it('lists posts with their status and URL', async () => {
    render(<BlogPosts />);
    expect(await screen.findByText('Sofa stand guide')).toBeInTheDocument();
    expect(screen.getByText('/blog/webbing-tips/')).toBeInTheDocument();
    const liveRow = screen.getByText('Sofa stand guide').closest('tr');
    const draftRow = screen.getByText('Webbing tips').closest('tr');
    expect(within(liveRow).getByText('Published')).toBeInTheDocument();
    expect(within(draftRow).getByText('Draft')).toBeInTheDocument();
  });

  it('shows an empty state with a call to action', async () => {
    cmsAPI.listPosts.mockResolvedValue({ data: { results: [] } });
    render(<BlogPosts />);
    expect(await screen.findByText('No blog posts yet')).toBeInTheDocument();
  });

  it('filters by status', async () => {
    render(<BlogPosts />);
    await screen.findByText('Sofa stand guide');
    fireEvent.click(screen.getByRole('button', { name: 'Drafts' }));
    await waitFor(() =>
      expect(cmsAPI.listPosts).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'draft' })),
    );
  });

  it('publishes and unpublishes a post', async () => {
    render(<BlogPosts />);
    await screen.findByText('Webbing tips');
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    await waitFor(() => expect(cmsAPI.updatePost).toHaveBeenCalledWith(2, { status: 'published' }));
    fireEvent.click(screen.getByRole('button', { name: 'Unpublish' }));
    await waitFor(() => expect(cmsAPI.updatePost).toHaveBeenCalledWith(1, { status: 'draft' }));
  });

  it('blocks saving an empty post and creates a valid one', async () => {
    render(<BlogPosts />);
    await screen.findByText('Sofa stand guide');
    fireEvent.click(screen.getByRole('button', { name: /New post/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Save draft' }));
    expect(await screen.findByText('Title is required.')).toBeInTheDocument();
    expect(cmsAPI.createPost).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Zipper sizes' } });
    fireEvent.change(screen.getByLabelText('Content'), { target: { value: '## No. 5\nFor cushions.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(cmsAPI.createPost).toHaveBeenCalledTimes(1));
    const data = cmsAPI.createPost.mock.calls[0][0];
    expect(data.get('title')).toBe('Zipper sizes');
    expect(data.get('status')).toBe('draft');
    expect(toast.success).toHaveBeenCalledWith('Draft saved');
  });

  it('deletes after confirmation', async () => {
    render(<BlogPosts />);
    await screen.findByText('Sofa stand guide');
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0]);
    const confirmButtons = await screen.findAllByRole('button', { name: 'Delete' });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);
    await waitFor(() => expect(cmsAPI.deletePost).toHaveBeenCalledWith(1));
  });
});
