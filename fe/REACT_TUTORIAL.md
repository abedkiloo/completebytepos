# React.js: Basics to Advanced (Using CompleteByte POS Frontend)

A practical guide to React using the code you’ve already built in this project. Each concept is tied to a real file and pattern in your app.

---

## Part 1: React basics

### 1.1 What is React?

React is a library for building UIs with **components**: small, reusable pieces that describe what the UI should look like and how it should behave. Your app is a tree of components (e.g. `App` → `Layout` → `Dashboard`, `Inventory`, etc.).

**In your app:** `fe/src/index.js` is the entry: it finds the DOM node `#root` and renders `<App />` into it. Everything else is inside `App`.

```7:12:fe/src/index.js
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

---

### 1.2 Components and JSX

A **component** is a function that returns JSX (HTML-like syntax). JSX gets compiled to `React.createElement` calls.

**Example from your app – `ConfirmDialog`:**

```4:26:fe/src/components/ConfirmDialog/ConfirmDialog.js
const ConfirmDialog = ({ isOpen, title, message, onConfirm, onCancel, confirmText = 'Confirm', cancelText = 'Cancel', type = 'danger' }) => {
  if (!isOpen) return null;

  return (
    <div className="confirm-dialog-overlay" onClick={onCancel}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-dialog-header">
          <h3>{title || 'Confirm Action'}</h3>
        </div>
        ...
      </div>
    </div>
  );
};
```

- **Function component:** `ConfirmDialog` is a function that returns JSX.
- **Props:** `isOpen`, `title`, `message`, `onConfirm`, etc. are **props** (inputs from the parent).
- **Default props:** `confirmText = 'Confirm'` gives a default if the parent doesn’t pass it.
- **Conditional return:** `if (!isOpen) return null` means “render nothing” when the dialog is closed.
- **`className`:** In JSX you use `className` instead of `class`.
- **`{expression}`:** Curly braces embed JavaScript (e.g. `{title || 'Confirm Action'}`).

---

### 1.3 State with `useState`

State is data that can change over time. When state changes, React re-renders the component.

**Example – Login form:**

```6:10:fe/src/components/Auth/Login.js
const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
```

- **`useState(initialValue)`** returns `[value, setter]`.
- **Updating state:** Call the setter (e.g. `setUsername(e.target.value)`). Never assign to the variable directly.
- **One piece of logic per state:** You have separate state for username, password, error, and loading. That keeps each concern clear.

**Controlled inputs:** The input’s value comes from state; changes go back into state:

```57:61:fe/src/components/Auth/Login.js
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
```

So: **React state is the single source of truth** for what’s in the input.

---

### 1.4 Events and forms

- **Event object:** Handlers receive an event (e.g. `e`). Use `e.preventDefault()` to stop form submit from reloading the page.
- **Form submit:** Handle `onSubmit` on the `<form>` and call `e.preventDefault()` in the handler.

**From Login:**

```12:20:fe/src/components/Auth/Login.js
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.login({ username, password });
      ...
```

So: prevent default → clear previous error → set loading → call API.

---

## Part 2: Side effects and data loading

### 2.1 `useEffect` – when to run code

Use **`useEffect`** when you need to run code **after** render (e.g. fetch data, subscribe to something, touch the DOM).

**Signature:** `useEffect(() => { ... }, [dependencies])`

- Runs after the first render and again whenever a dependency in the array changes.
- Empty array `[]` = run once after mount.
- No array = run after every render (use sparingly).

**Example – load products when `product` prop changes (StockPurchaseModal):**

```22:36:fe/src/components/Inventory/StockPurchaseModal.js
  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      const qty = (product.reorder_quantity != null && product.reorder_quantity > 0)
        ? product.reorder_quantity
        : 1;
      setFormData(prev => ({
        ...prev,
        product_id: product.id,
        quantity: qty,
        unit_cost: product.cost || '',
      }));
    }
  }, [product]);
```

- **Dependency `[product]`:** When `product` changes (e.g. user opens modal for another product), the effect runs again.
- **Functional updates:** `setFormData(prev => ({ ...prev, ... }))` uses the latest state and avoids stale closures.

**Example – subscribe and cleanup (App toasts):**

```43:50:fe/src/App.js
  useEffect(() => {
    // Subscribe to toast notifications globally
    const unsubscribe = subscribeToToasts((newToast) => {
      setToasts(prev => [...prev, newToast]);
    });
    
    return () => unsubscribe();
  }, []);
```

- **Cleanup:** Returning a function from `useEffect` runs it when the component unmounts (or before the effect runs again). Here it unsubscribes from toasts.

---

### 2.2 Loading data on mount and when filters change

**From Inventory:**

```69:90:fe/src/components/Inventory/Inventory.js
  useEffect(() => {
    loadData();
  }, [filters, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'movements') {
        await loadMovements();
      } else if (activeTab === 'low_stock') {
        await loadLowStock();
      } ...
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };
```

- **When it runs:** On mount and whenever `filters` or `activeTab` change.
- **Pattern:** `setLoading(true)` → async work → `setState` with result → `setLoading(false)` in `finally`. Always handle errors (e.g. try/catch, set error state or show toast).

---

## Part 3: Lists, keys, and conditional rendering

### 3.1 Rendering lists and the `key` prop

When you render an array with `.map()`, each top-level element must have a **unique `key`** (usually an id). Keys help React track which items changed.

**ToastContainer:**

```6:16:fe/src/components/Toast/ToastContainer.js
const ToastContainer = ({ toasts, removeToast }) => {
  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onClose={() => removeToast(toast.id)}
          duration={toast.duration}
        />
      ))}
```

- **`key={toast.id}`** – stable, unique id. Don’t use array index as key if the list can be reordered or filtered.

### 3.2 Conditional rendering

- **Early return:** `if (!isOpen) return null` in ConfirmDialog.
- **Ternary:** `condition ? <A /> : <B />`
- **Short-circuit:** `condition && <Component />` (when you don’t need an else).

**Layout – show section only if module is enabled:**

```284:299:fe/src/components/Layout/Layout.js
            {isModuleEnabled('products') && (
              <div className="sidebar-section" ...>
                ...
                {expandedSections.inventory && (
                  <div className="section-items">
                    <Link to="/products" ...>Products</Link>
                    ...
```

---

## Part 4: Routing (React Router)

Your app uses **react-router-dom**: URLs map to components, and you get navigation without full page reloads.

### 4.1 Setup (App.js)

```56:69:fe/src/App.js
    <Router>
      <div className="App">
        <ToastContainer toasts={toasts} removeToast={removeToast} />
        <Routes>
          <Route path="/install" element={<Installation />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
```

- **`Router`** wraps the app (usually `BrowserRouter` as `Router`).
- **`Routes` / `Route`:** `path` + `element` define which component renders for a URL.
- **Nested protection:** `ProtectedRoute` wraps `Dashboard` so only authenticated users see it.

### 4.2 Protected routes

```33:38:fe/src/App.js
const ProtectedRoute = ({ children }) => {
  const accessToken = localStorage.getItem('access_token');
  const isAuthenticated = accessToken && localStorage.getItem('isAuthenticated') === 'true';
  return isAuthenticated ? children : <Navigate to="/login" />;
};
```

- If not authenticated, render **`<Navigate to="/login" />`** (redirect).
- Otherwise render **`children`** (the actual page).

### 4.3 Navigation and URL

- **Declarative link:** `<Link to="/products">Products</Link>` – use for in-app links.
- **Programmatic:** `const navigate = useNavigate(); navigate('/');` – e.g. after login.
- **Current location:** `const location = useLocation();` – e.g. `location.pathname`, `location.search` (query string).

**Inventory reading URL params:**

```49:67:fe/src/components/Inventory/Inventory.js
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const action = params.get('action');
    const view = params.get('view');

    if (action === 'adjust' && ...) {
      setShowAdjustmentModal(true);
      navigate('/inventory', { replace: true });
    } else if (action === 'transfer' && ...) {
      setShowTransferModal(true);
      navigate('/inventory', { replace: true });
    } ...
  }, [location.search, navigate]);
```

So: read `?action=adjust` or `?view=movements`, update state (e.g. open modal), then clean the URL with `navigate(..., { replace: true })`.

---

## Part 5: Connecting to the backend

### 5.1 Central API client (fe/src/services/api.js)

Your app uses **axios** with a shared instance and base URL:

```65:67:fe/src/services/api.js
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: defaultHeaders,
});
```

**Base URL resolution** (simplified):

- `REACT_APP_API_URL` (env or `window`) → used if set.
- HTTPS/ngrok → can use `localStorage.getItem('backend_ngrok_url')` or fallback.
- Same host, different port → e.g. `${protocol}//${hostname}:8000/api`.
- Local dev → `http://localhost:8000/api`.

So: **one place** defines where the backend is; all API calls go through this client.

### 5.2 Attaching the JWT (request interceptor)

```75:80:fe/src/services/api.js
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
```

Every request gets the token from `localStorage` and adds `Authorization: Bearer <token>`. You never attach the token manually in each component.

### 5.3 Handling 401 and token refresh (response interceptor)

```143:206:fe/src/services/api.js
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config || {};

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        ...
        const response = await axios.post(`${API_BASE_URL}/token/refresh/`, { refresh: refreshToken }, ...);
        const { access } = response.data;
        localStorage.setItem('access_token', access);
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return api(originalRequest);  // retry original request
      } catch (refreshError) {
        // logout and redirect to /login
        ...
        window.location.href = '/login';
      }
    }
    ...
  }
);
```

- **401:** Try to refresh the access token once (`_retry` prevents loops).
- **Success:** Save new access token, retry the original request.
- **Failure:** Clear auth and redirect to login.

So: components don’t need to handle 401/refresh; the interceptor does it in one place.

### 5.4 Using the API in components

**Structured endpoints** – e.g. products:

```212:232:fe/src/services/api.js
export const productsAPI = {
  list: (params) => api.get('/products/', { params }),
  get: (id) => api.get(`/products/${id}/`),
  create: (data) => api.post('/products/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  update: (id, data) => api.put(`/products/${id}/`, data, ...),
  delete: (id) => api.delete(`/products/${id}/`),
  ...
};
```

**In a component:**

```37:51:fe/src/components/Inventory/StockPurchaseModal.js
  const loadProducts = async () => {
    try {
      const params = { track_stock: 'true', is_active: 'true', page_size: 1000, needs_restock: 'true' };
      const response = await productsAPI.list(params);
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
    }
  };
```

- **Always:** `try/catch`, handle both success shape (`results` vs `data`) and errors (log, set error state, or toast).

---

## Part 6: Slightly more advanced patterns

### 6.1 Refs: `useRef`

**Use refs for:** DOM nodes, or any value that should persist across renders without causing re-renders when it changes.

**SearchableSelect – click-outside and focus:**

```17:19:fe/src/components/Shared/SearchableSelect.js
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };
    ...
    if (inputRef.current && searchable) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
```

- **`dropdownRef.current`** – the DOM element you attached with `ref={dropdownRef}`.
- **`inputRef.current?.focus()`** – imperative focus when the dropdown opens. Optional chaining avoids errors if the ref isn’t set yet.

**Layout – timeout for hover:**

```29:30:fe/src/components/Layout/Layout.js
  const hoverTimeoutRef = useRef(null);
  ...
  if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
  hoverTimeoutRef.current = setTimeout(() => setHoveredSection(section), 100);
```

Storing the timeout in a ref keeps it across re-renders and allows cleanup on unmount.

### 6.2 Reusable components and props

**ConfirmDialog** is fully controlled by props: `isOpen`, `title`, `message`, `onConfirm`, `onCancel`, etc. The parent owns state and passes callbacks.

**SearchableSelect** – controlled value + options + callbacks:

```4:15:fe/src/components/Shared/SearchableSelect.js
const SearchableSelect = ({
  value,
  onChange,
  options = [],
  placeholder = 'Select...',
  disabled = false,
  searchable = true,
  onAddNew,
  addNewLabel = '+ Add New',
  className = '',
  name = '',
}) => {
```

So: **controlled component** – parent holds `value`, passes `onChange`; the select only reports changes.

### 6.3 Composition: `children`

**Layout** wraps page content:

```9:9:fe/src/components/Layout/Layout.js
const Layout = ({ children }) => {
```

Usage: `<Layout><Dashboard /></Layout>`. So **`children`** is whatever you put between the opening and closing tags. Different pages pass different content; Layout provides header/sidebar and renders `{children}` in the main area.

### 6.4 Global-ish behavior without Redux: toast subscription

**Toast flow:**

1. **`utils/toast.js`:** `showToast(message, type)` notifies all registered listeners. `subscribeToToasts(listener)` adds a listener and returns an unsubscribe function.
2. **App:** Subscribes in `useEffect`, pushes new toasts into state, renders `ToastContainer`.
3. **Any component:** Imports `toast` and calls `toast.success('Saved!')` or `toast.error('Failed')`. No need to pass callbacks down the tree.

So: a small **pub/sub** pattern gives app-wide toasts without global state libraries.

---

## Part 7: Troubleshooting and where errors come from

### 7.1 Checklist: “Nothing loads / blank screen”

| Check | Where | What to do |
|-------|--------|------------|
| **API base URL** | Browser console on load | Look for `[API] Using API Base URL: ...`. If wrong or missing, set `REACT_APP_API_URL` or fix `api.js` logic. |
| **Backend running** | Terminal / backend URL | Ensure Django (or your backend) is running on the port used by `API_BASE_URL` (e.g. 8000). |
| **CORS** | Network tab, failed request | Backend must allow your frontend origin. Add frontend URL to CORS allowed origins in Django (e.g. `CORS_ALLOWED_ORIGINS` or `corsheaders`). |
| **401 on every request** | Network tab | Token missing or invalid. Check localStorage: `access_token`, `isAuthenticated`. Re-login. |
| **React crash** | Console (red error) | Read the stack trace. Often: undefined property (e.g. `response.data.results` when `data` is null), or missing key in list. |

### 7.2 Typical error sources in your codebase

1. **Response shape**  
   Backend sometimes returns `{ results: [...] }`, sometimes a plain array. Your code often does:  
   `response.data.results || response.data || []`  
   If you assume only one shape, you can get `undefined` and then e.g. `.map is not a function`. **Fix:** Normalize in one place (e.g. `const list = response.data?.results ?? response.data ?? [];` and ensure it’s always an array).

2. **Optional chaining**  
   If `product` or `response.data` can be null/undefined, use `product?.id`, `response.data?.results`. Otherwise a single null from the API can crash the whole tree.

3. **useEffect dependencies**  
   If you use a function or value inside `useEffect` that comes from props/state, list it in the dependency array. Missing deps can cause stale data or infinite loops. ESLint rule `exhaustive-deps` helps.

4. **Async state updates**  
   After an async call, the component might already be unmounted. Avoid `setState` on unmounted components (e.g. use an `isMounted` flag or ignore aborted updates in cleanup).

### 7.3 Network and backend

- **DevTools → Network:** Filter by “Fetch/XHR”. Check status (200, 401, 404, 500), request URL (correct base URL + path?), and request headers (`Authorization` present when needed).
- **Console:** Look for `[API]` logs and any `Error loading ...` from your catch blocks. That tells you which request failed.
- **Backend URL on HTTPS/ngrok:** If frontend is HTTPS/ngrok, backend must be too (or you’ll get mixed content or CORS). Set `backend_ngrok_url` or `REACT_APP_API_URL` to the backend’s HTTPS URL. The ngrok-skip-browser-warning header is already set in your api when the base URL contains `ngrok`.

### 7.4 Auth-specific

- **Infinite redirect** (login → “/” → login): ProtectedRoute checks `access_token` and `isAuthenticated`. If login doesn’t set both, or logout doesn’t clear them, you get loops. Check Login’s `localStorage.setItem('isAuthenticated', 'true')` and logout clearing both.
- **401 on login:** Wrong credentials or backend auth endpoint. Check `err.response?.data` in Login’s catch; backend often returns `{ detail: '...' }` or `{ error: '...' }`. Your code uses `err.response?.data?.error || err.response?.data?.detail`.

### 7.5 Quick debug pattern

In any component that fetches:

```js
const loadData = async () => {
  setLoading(true);
  setError('');
  try {
    const response = await someAPI.list(params);
    console.log('API response', response.data);  // temporary
    setItems(response.data.results ?? response.data ?? []);
  } catch (err) {
    console.error('API error', err.response?.status, err.response?.data, err.message);
    setError(err.response?.data?.detail || err.message || 'Request failed');
    setItems([]);
  } finally {
    setLoading(false);
  }
};
```

Then: check console for “API response” / “API error”, and Network for the same request. That usually tells you if the problem is URL, auth, payload, or response shape.

---

## Summary map (concept → where in your app)

| Concept | Example in your app |
|--------|----------------------|
| Entry & root | `index.js` – `createRoot`, `render(<App />)` |
| Components & JSX | `ConfirmDialog.js`, any `*.js` in `components/` |
| Props & defaults | `ConfirmDialog` props, `SearchableSelect` options |
| State | `useState` in Login, StockPurchaseModal, Inventory, Layout |
| Events & forms | Login `handleSubmit`, `onChange` on inputs |
| Side effects | `useEffect` in App (toast), StockPurchaseModal (product), Inventory (loadData), Layout (resize, modules) |
| Lists & keys | ToastContainer `toasts.map` with `key={toast.id}` |
| Conditional render | `isOpen &&`, `isModuleEnabled() &&`, `expandedSections.main &&` in Layout |
| Routing | App.js `Routes`/`Route`, `ProtectedRoute`, `Navigate` |
| Link / navigate | Layout `Link`, Login `navigate('/')`, Inventory `navigate('/inventory', { replace: true })` |
| URL params | Inventory `useLocation().search`, `URLSearchParams` |
| API client | `services/api.js` – axios instance, interceptors, `productsAPI`, `inventoryAPI`, etc. |
| Using API in UI | Login `authAPI.login`, StockPurchaseModal `productsAPI.list`, Inventory `inventoryAPI.list` |
| Refs | SearchableSelect `dropdownRef`/`inputRef`, Layout `hoverTimeoutRef` |
| Composition | Layout `children`, ConfirmDialog/SearchableSelect as reusable building blocks |
| Cross-component “global” behavior | Toast: `subscribeToToasts` in App, `toast.success()` anywhere |

Use this doc as a map: when you see a pattern in the codebase, you can match it to the concept here and vice versa. For deeper dives, read the specific files referenced in each section.
