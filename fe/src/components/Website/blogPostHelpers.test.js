import {
  EMPTY_POST,
  apiErrorMessage,
  buildPostFormData,
  postToForm,
  validatePostForm,
} from './blogPostHelpers';

describe('blogPostHelpers', () => {
  it('postToForm fills defaults and ignores unknown/null fields', () => {
    expect(postToForm(null)).toEqual(EMPTY_POST);
    const form = postToForm({ id: 3, title: 'Hi', excerpt: null, is_featured: true, author: 1 });
    expect(form.title).toBe('Hi');
    expect(form.excerpt).toBe('');
    expect(form.is_featured).toBe(true);
    expect(form).not.toHaveProperty('id');
    expect(form).not.toHaveProperty('author');
  });

  it('validatePostForm flags required fields, slug format and SEO lengths', () => {
    const errors = validatePostForm({
      ...EMPTY_POST,
      slug: 'Bad Slug!',
      meta_title: 'x'.repeat(71),
      meta_description: 'x'.repeat(161),
    });
    expect(Object.keys(errors).sort()).toEqual(
      ['body', 'meta_description', 'meta_title', 'slug', 'title'],
    );
    expect(validatePostForm({ ...EMPTY_POST, title: 'T', body: 'B', slug: 'ok-slug-2' })).toEqual({});
  });

  it('buildPostFormData serialises booleans and cover handling', () => {
    const file = new File(['x'], 'c.png', { type: 'image/png' });
    const withFile = buildPostFormData({ ...EMPTY_POST, title: 'T', is_featured: true }, { coverFile: file, removeCover: true });
    expect(withFile.get('title')).toBe('T');
    expect(withFile.get('is_featured')).toBe('true');
    expect(withFile.get('cover_image')).toBe(file);
    expect(withFile.get('remove_cover_image')).toBeNull();

    const removing = buildPostFormData({ ...EMPTY_POST }, { removeCover: true });
    expect(removing.get('remove_cover_image')).toBe('true');
    expect(removing.get('cover_image')).toBeNull();
  });

  it('apiErrorMessage picks the most useful message', () => {
    expect(apiErrorMessage({})).toBe('Could not save the post.');
    expect(apiErrorMessage({ response: { data: { detail: 'Nope' } } })).toBe('Nope');
    expect(apiErrorMessage({ response: { data: { slug: ['Taken'] } } })).toBe('slug: Taken');
    expect(apiErrorMessage({ response: { data: { non_field_errors: ['Bad'] } } })).toBe('Bad');
  });
});
