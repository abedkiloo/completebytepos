import React, { useState } from 'react';
import { cmsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  META_DESCRIPTION_MAX,
  META_TITLE_MAX,
  apiErrorMessage,
  buildPostFormData,
  postToForm,
  validatePostForm,
} from './blogPostHelpers';

const textareaClass =
  'w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm ' +
  'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function Field({ id, label, hint, error, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

const BlogPostForm = ({ post, onClose, onSaved }) => {
  const [form, setForm] = useState(() => postToForm(post));
  const [errors, setErrors] = useState({});
  const [coverFile, setCoverFile] = useState(null);
  const [removeCover, setRemoveCover] = useState(false);
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const found = validatePostForm(form);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const data = buildPostFormData(form, { coverFile, removeCover });
      const res = post?.id
        ? await cmsAPI.updatePost(post.id, data)
        : await cmsAPI.createPost(data);
      toast.success(form.status === 'published' ? 'Post published' : 'Draft saved');
      onSaved(res.data);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" description="Write a blog post for the public website">
        <DialogHeader>
          <DialogTitle>{post?.id ? 'Edit post' : 'New blog post'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <Field id="post-title" label="Title" error={errors.title}>
            <Input id="post-title" value={form.title} onChange={set('title')} placeholder="How to choose the right sofa stand" />
          </Field>
          <Field
            id="post-excerpt"
            label="Short summary"
            hint="One or two sentences shown on the blog list."
          >
            <Input id="post-excerpt" value={form.excerpt} onChange={set('excerpt')} maxLength={300} />
          </Field>
          <Field
            id="post-body"
            label="Content"
            hint="Use ## for headings, **bold**, - for lists and [text](https://link) for links."
            error={errors.body}
          >
            <textarea id="post-body" rows={12} className={textareaClass} value={form.body} onChange={set('body')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="post-tags" label="Tags" hint="Comma-separated, e.g. zippers, sofa stands">
              <Input id="post-tags" value={form.tags} onChange={set('tags')} />
            </Field>
            <Field id="post-slug" label="Web address (optional)" hint="Left blank, it is made from the title." error={errors.slug}>
              <Input id="post-slug" value={form.slug} onChange={set('slug')} placeholder="choose-sofa-stand" />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="post-cover" label="Cover image" hint={post?.cover_image_url && !coverFile ? 'A cover is already uploaded.' : 'JPG or PNG, landscape works best.'}>
              <Input id="post-cover" type="file" accept="image/*" onChange={(e) => setCoverFile(e.target.files?.[0] || null)} />
              {post?.cover_image_url && !coverFile && (
                <label className="mt-1 flex items-center gap-2 text-xs">
                  <input type="checkbox" checked={removeCover} onChange={(e) => setRemoveCover(e.target.checked)} />
                  Remove current cover
                </label>
              )}
            </Field>
            <Field id="post-cover-alt" label="Cover description" hint="Describes the photo for Google and screen readers.">
              <Input id="post-cover-alt" value={form.cover_image_alt} onChange={set('cover_image_alt')} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="post-meta-title" label={`Google title (${form.meta_title.length}/${META_TITLE_MAX})`} error={errors.meta_title} hint="Optional — defaults to the post title.">
              <Input id="post-meta-title" value={form.meta_title} onChange={set('meta_title')} />
            </Field>
            <Field id="post-meta-description" label={`Google description (${form.meta_description.length}/${META_DESCRIPTION_MAX})`} error={errors.meta_description} hint="Optional — defaults to the summary.">
              <Input id="post-meta-description" value={form.meta_description} onChange={set('meta_description')} />
            </Field>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <span className="font-medium">Status</span>
              <select aria-label="Status" className="h-9 rounded-md border border-input bg-background px-2 text-sm" value={form.status} onChange={set('status')}>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_featured} onChange={set('is_featured')} />
              Feature on the website home page
            </label>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : form.status === 'published' ? 'Publish' : 'Save draft'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default BlogPostForm;
