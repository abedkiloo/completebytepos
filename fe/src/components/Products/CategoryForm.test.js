import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import CategoryForm from './CategoryForm';
import { categoriesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  categoriesAPI: { create: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../Shared/SearchableSelect', () => (props) => (
  <select
    data-testid="parent-select"
    name={props.name}
    value={props.value}
    onChange={props.onChange}
  >
    {(props.options || []).map((opt) => (
      <option key={String(opt.id)} value={String(opt.id)}>
        {opt.name}
      </option>
    ))}
  </select>
));

describe('CategoryForm nested pane', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('renders nothing when closed', () => {
    render(<CategoryForm isOpen={false} onClose={jest.fn()} onSave={jest.fn()} />);
    expect(screen.queryByRole('heading', { name: 'Add category' })).not.toBeInTheDocument();
  });

  it('stays open if the overlay is clicked immediately after opening', () => {
    const onClose = jest.fn();
    render(<CategoryForm isOpen onClose={onClose} onSave={jest.fn()} categories={[]} />);

    expect(screen.getByRole('heading', { name: 'Add category' })).toBeInTheDocument();
    fireEvent.click(document.querySelector('.slide-in-overlay'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes from the overlay after the opening click has settled', () => {
    const onClose = jest.fn();
    render(<CategoryForm isOpen onClose={onClose} onSave={jest.fn()} categories={[]} />);

    act(() => {
      jest.advanceTimersByTime(350);
    });
    fireEvent.mouseDown(document.querySelector('.slide-in-overlay'));
    fireEvent.click(document.querySelector('.slide-in-overlay'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not close when the panel itself is clicked', () => {
    const onClose = jest.fn();
    render(<CategoryForm isOpen onClose={onClose} onSave={jest.fn()} categories={[]} />);

    act(() => {
      jest.advanceTimersByTime(350);
    });
    fireEvent.click(document.querySelector('.slide-in-panel'));
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('CategoryForm submit', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('creates a category and optional parent', async () => {
    categoriesAPI.create.mockResolvedValue({ data: { id: 9, name: 'Soda' } });
    const onSave = jest.fn();
    const onClose = jest.fn();
    render(
      <CategoryForm
        isOpen
        onClose={onClose}
        onSave={onSave}
        categories={[{ id: 1, name: 'Drinks', parent: null }]}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: 'Soda' },
    });
    fireEvent.change(screen.getByPlaceholderText('Optional description'), {
      target: { name: 'description', value: 'Cold drinks' },
    });
    fireEvent.change(screen.getByTestId('parent-select'), {
      target: { name: 'parent', value: '1' },
    });
    fireEvent.click(screen.getByLabelText('Active'));
    fireEvent.click(screen.getByLabelText('Active'));
    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));

    await waitFor(() => {
      expect(categoriesAPI.create).toHaveBeenCalledWith({
        name: 'Soda',
        description: 'Cold drinks',
        is_active: true,
        parent: 1,
      });
    });
    expect(toast.success).toHaveBeenCalled();
    expect(onSave).toHaveBeenCalledWith({ id: 9, name: 'Soda' });
    expect(onClose).toHaveBeenCalled();
  });

  it('requires a name', async () => {
    render(<CategoryForm isOpen onClose={jest.fn()} onSave={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));
    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: 'Water' },
    });
    expect(screen.queryByText('Name is required')).not.toBeInTheDocument();
    expect(categoriesAPI.create).not.toHaveBeenCalled();
  });

  it('creates a subcategory and resolves duplicates', async () => {
    categoriesAPI.create.mockRejectedValueOnce({
      response: { data: { name: ['Soda already exists as a subcategory'] } },
    });
    const onResolveDuplicate = jest.fn().mockResolvedValue(true);
    render(
      <CategoryForm
        isOpen
        onClose={jest.fn()}
        onSave={jest.fn()}
        parentCategory={3}
        initialName="Soda"
        categories={[{ id: 3, name: 'Drinks', parent: null }]}
        onResolveDuplicate={onResolveDuplicate}
      />
    );

    expect(screen.getByRole('heading', { name: 'Add subcategory' })).toBeInTheDocument();
    expect(screen.getByDisplayValue('Drinks')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create subcategory' }));

    await waitFor(() => {
      expect(onResolveDuplicate).toHaveBeenCalledWith('Soda');
    });
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('shows API errors and network errors', async () => {
    categoriesAPI.create
      .mockRejectedValueOnce({ response: { data: { error: 'Duplicate name' } } })
      .mockRejectedValueOnce(new Error('offline'));

    const { rerender } = render(
      <CategoryForm isOpen onClose={jest.fn()} onSave={jest.fn()} />
    );
    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: 'Tea' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Duplicate name');
    });

    rerender(<CategoryForm isOpen onClose={jest.fn()} onSave={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: 'Tea' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to create category: offline');
    });
  });

  it('shows parent fallback name when the category list has no match', () => {
    render(
      <CategoryForm
        isOpen
        onClose={jest.fn()}
        parentCategory={99}
        categories={[]}
      />
    );
    expect(screen.getByRole('heading', { name: 'Add subcategory' })).toBeInTheDocument();
  });

  it('creates a subcategory without a duplicate', async () => {
    categoriesAPI.create.mockResolvedValue({ data: { id: 12, name: 'Diet' } });
    const onSave = jest.fn();
    render(
      <CategoryForm
        isOpen
        onClose={jest.fn()}
        onSave={onSave}
        parentCategory={3}
        initialName="Diet"
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Create subcategory' }));
    await waitFor(() => {
      expect(categoriesAPI.create).toHaveBeenCalledWith({
        name: 'Diet',
        description: '',
        is_active: true,
        parent: 3,
      });
    });
    expect(toast.success).toHaveBeenCalledWith('Subcategory created successfully');
    expect(onSave).toHaveBeenCalledWith({ id: 12, name: 'Diet' });
  });

  it('toasts when a duplicate cannot be resolved', async () => {
    categoriesAPI.create.mockRejectedValue({
      response: { data: { name: 'Soda already exists as a subcategory' } },
    });
    const onResolveDuplicate = jest.fn().mockResolvedValue(false);
    render(
      <CategoryForm
        isOpen
        onClose={jest.fn()}
        parentCategory={3}
        initialName="Soda"
        onResolveDuplicate={onResolveDuplicate}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Create subcategory' }));
    await waitFor(() => {
      expect(onResolveDuplicate).toHaveBeenCalledWith('Soda');
    });
    expect(toast.error).toHaveBeenCalledWith('Soda already exists as a subcategory');
  });

  it('shows parent field errors and unknown network failures', async () => {
    categoriesAPI.create
      .mockRejectedValueOnce({ response: { data: { parent: ['Invalid parent'] } } })
      .mockRejectedValueOnce({});

    render(<CategoryForm isOpen onClose={jest.fn()} onSave={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Category name'), {
      target: { name: 'name', value: 'Juice' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Invalid parent');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Create category' }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to create category: Unknown error');
    });
  });
});
