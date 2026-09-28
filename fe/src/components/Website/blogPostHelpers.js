/** Pure helpers for the blog post editor (kept separate so they are easy to test). */

export const META_TITLE_MAX = 70;
export const META_DESCRIPTION_MAX = 160;

export const EMPTY_POST = {
  title: '',
  slug: '',
  excerpt: '',
  body: '',
  tags: '',
  cover_image_alt: '',
  meta_title: '',
  meta_description: '',
  status: 'draft',
  is_featured: false,
};

export function postToForm(post) {
  if (!post) return { ...EMPTY_POST };
  const form = { ...EMPTY_POST };
  Object.keys(EMPTY_POST).forEach((key) => {
    if (post[key] !== undefined && post[key] !== null) form[key] = post[key];
  });
  return form;
}

export function validatePostForm(form) {
  const errors = {};
  if (!form.title.trim()) errors.title = 'Title is required.';
  if (!form.body.trim()) errors.body = 'Write the post content before saving.';
  if (form.slug && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(form.slug)) {
    errors.slug = 'Use lowercase letters, numbers and dashes only.';
  }
  if (form.meta_title.length > META_TITLE_MAX) {
    errors.meta_title = `Keep it under ${META_TITLE_MAX} characters.`;
  }
  if (form.meta_description.length > META_DESCRIPTION_MAX) {
    errors.meta_description = `Keep it under ${META_DESCRIPTION_MAX} characters.`;
  }
  return errors;
}

export function buildPostFormData(form, { coverFile = null, removeCover = false } = {}) {
  const data = new FormData();
  Object.keys(EMPTY_POST).forEach((key) => {
    const value = form[key];
    data.append(key, typeof value === 'boolean' ? String(value) : (value ?? ''));
  });
  if (coverFile) data.append('cover_image', coverFile);
  if (removeCover && !coverFile) data.append('remove_cover_image', 'true');
  return data;
}

export function apiErrorMessage(error, fallback = 'Could not save the post.') {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  const first = Object.entries(data)[0];
  if (!first) return fallback;
  const [field, msgs] = first;
  const msg = Array.isArray(msgs) ? msgs[0] : msgs;
  return field === 'non_field_errors' ? String(msg) : `${field}: ${msg}`;
}
