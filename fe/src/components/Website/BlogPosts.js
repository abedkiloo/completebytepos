import React, { useCallback, useEffect, useState } from 'react';
import { Newspaper, Plus } from 'lucide-react';
import { cmsAPI } from '../../services/api';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { Button } from '../ui/button';
import {
  EmptyState,
  FilterBar,
  FilterPills,
  PageHeader,
  PageLoading,
  PageShell,
  SearchField,
  StatusBadge,
} from '../page';
import BlogPostForm from './BlogPostForm';
import { apiErrorMessage } from './blogPostHelpers';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Drafts' },
];

const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

const BlogPosts = () => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page_size: 100 };
      if (status) params.status = status;
      if (debouncedSearch) params.search = debouncedSearch;
      const res = await cmsAPI.listPosts(params);
      const rows = res.data?.results ?? res.data ?? [];
      setPosts(Array.isArray(rows) ? rows : []);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Failed to load blog posts'));
    } finally {
      setLoading(false);
    }
  }, [status, debouncedSearch]);

  useEffect(() => {
    load();
  }, [load]);

  const togglePublish = async (post) => {
    const next = post.status === 'published' ? 'draft' : 'published';
    try {
      await cmsAPI.updatePost(post.id, { status: next });
      toast.success(next === 'published' ? 'Post published' : 'Post moved to drafts');
      load();
    } catch (error) {
      toast.error(apiErrorMessage(error));
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await cmsAPI.deletePost(deleting.id);
      toast.success('Post deleted');
      setDeleting(null);
      load();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Could not delete the post.'));
      setDeleting(null);
    }
  };

  if (loading && posts.length === 0 && !status && !debouncedSearch) {
    return <PageLoading rows={5} />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Blog posts"
        description="Articles for the public Omuwenga Suppliers website. Published posts appear on the site's blog."
      >
        <Button onClick={() => setEditing({})}>
          <Plus className="h-4 w-4" />
          New post
        </Button>
      </PageHeader>

      <FilterBar>
        <SearchField
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title or tag…"
        />
        <FilterPills options={STATUS_OPTIONS} value={status} onChange={setStatus} />
      </FilterBar>

      {posts.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title="No blog posts yet"
          description="Share buying tips, new stock and workshop guides with fundis and furniture makers."
          actionLabel="Write the first post"
          onAction={() => setEditing({})}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">Title</th>
                <th className="text-left">Status</th>
                <th className="text-left">Published</th>
                <th className="text-left">Updated</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => (
                <tr key={post.id}>
                  <td>
                    <div className="font-medium">{post.title}</div>
                    <div className="text-xs text-muted-foreground">/blog/{post.slug}/</div>
                  </td>
                  <td>
                    <StatusBadge status={post.status} label={post.status === 'published' ? 'Published' : 'Draft'} />
                  </td>
                  <td>{formatDate(post.published_at)}</td>
                  <td>{formatDate(post.updated_at)}</td>
                  <td>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => setEditing(post)}>Edit</Button>
                      <Button size="sm" variant="outline" onClick={() => togglePublish(post)}>
                        {post.status === 'published' ? 'Unpublish' : 'Publish'}
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => setDeleting(post)}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <BlogPostForm
          post={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      <ConfirmDialog
        isOpen={Boolean(deleting)}
        title="Delete post"
        message={`Delete "${deleting?.title}"? It will disappear from the website.`}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
    </PageShell>
  );
};

export default BlogPosts;
