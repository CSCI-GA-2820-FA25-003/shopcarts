const API_BASE = "/api/shopcarts";
const actionEndpoints = {
  checkout: "checkout",
  cancel: "cancel",
  lock: "lock",
  expire: "expire",
  reactivate: "reactivate",
};

const alertsRegion = document.querySelector("#alerts");
const resultCard = document.querySelector("#result-card");
const tableBody = document.querySelector("#shopcart-table tbody");
const clearFiltersBtn = document.querySelector("#clear-filters");
const queryForm = document.querySelector("#query-form");
const listFilterForm = document.querySelector("#list-filter");
const listResetFilterBtn = document.querySelector("#list-reset-filter");
const itemTableBody = document.querySelector("#item-table tbody");

const forms = {
  create: document.querySelector("#create-form"),
  update: document.querySelector("#update-form"),
  read: document.querySelector("#read-form"),
  delete: document.querySelector("#delete-form"),
  action: document.querySelector("#action-form"),
};

const itemForms = {
  add: document.querySelector("#item-add-form"),
  update: document.querySelector("#item-update-form"),
  delete: document.querySelector("#item-delete-form"),
  read: document.querySelector("#item-read-form"),
  list: document.querySelector("#item-list-form"),
};

const formatCurrency = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(Number(value ?? 0));

const formatDate = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const showAlert = (message, variant = "info") => {
  alertsRegion.innerHTML = `<div class="alert ${variant}">${message}</div>`;
};

const clearAlert = () => {
  alertsRegion.innerHTML = "";
};

const normalizeStatus = (value) =>
  (value ?? "active").toString().trim().toLowerCase() || "active";

const STATUS_DISPLAY = {
  active: "ACTIVE",
  abandoned: "ABANDONED",
  locked: "LOCKED",
  expired: "EXPIRED",
};

const formatStatusLabel = (value) =>
  STATUS_DISPLAY[normalizeStatus(value)] ||
  normalizeStatus(value).toUpperCase();

const normalizeCart = (raw = {}) => {
  if (!raw || typeof raw !== "object") return null;
  const snake = "customer_id" in raw || "total_items" in raw;
  const items = raw.items ?? [];
  const computeTotals = () =>
    items.reduce(
      (acc, item) =>
        acc + Number(item.price ?? item.unit_price ?? 0) * Number(item.quantity ?? 0),
      0
    );
  return {
    customerId: snake ? raw.customer_id : raw.customerId ?? raw.id,
    name: raw.name ?? raw.cartName ?? "",
    status: normalizeStatus(raw.status),
    statusDisplay: formatStatusLabel(raw.status),
    totalItems: snake ? raw.total_items ?? items.length : raw.totalItems ?? 0,
    totalPrice: raw.total_price ?? raw.totalPrice ?? computeTotals(),
    createdDate: snake ? raw.created_date : raw.createdDate,
    lastModified: snake ? raw.last_modified : raw.lastModified,
    items,
  };
};

const renderShopcartCard = (cart) => {
  if (!cart) {
    renderItemsTable([]);
    resultCard.hidden = true;
    resultCard.innerHTML = "";
    return;
  }
  const badgeClass = `badge ${cart.status}`;
  const itemsHtml =
    cart.items && cart.items.length
      ? `<table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            ${cart.items
              .map(
                (item) => `<tr>
                  <td>${item.product_id ?? item.productId}</td>
                  <td>${item.description ?? "—"}</td>
                  <td>${item.quantity ?? 0}</td>
                  <td>${formatCurrency(item.price)}</td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>`
      : "<p>No line items in this cart yet.</p>";
  resultCard.hidden = false;
  resultCard.innerHTML = `
    <h3>Customer ${cart.customerId}</h3>
    <p><span class="${badgeClass}">${cart.statusDisplay}</span></p>
    <div class="metadata">
      <div><span>Name</span>${cart.name || "—"}</div>
      <div><span>Total Items</span>${cart.totalItems}</div>
      <div><span>Total Price</span>${formatCurrency(cart.totalPrice)}</div>
      <div><span>Created</span>${formatDate(cart.createdDate)}</div>
      <div><span>Updated</span>${formatDate(cart.lastModified)}</div>
    </div>
    <div class="card-actions destructive">
      <button
        type="button"
        class="delete-cart"
        data-delete-cart
        data-customer-id="${cart.customerId}"
        aria-label="Delete cart ${cart.customerId}"
      >
        Delete Cart
      </button>
    </div>
    <div class="items">${itemsHtml}</div>
  `;
  bindResultCardActions(cart);
  renderItemsTable(cart.items || []);
};

const renderTable = (carts) => {
  if (!Array.isArray(carts) || carts.length === 0) {
    tableBody.innerHTML =
      '<tr><td colspan="7" class="empty">No results match your filters.</td></tr>';
      
    return;
  }

  tableBody.innerHTML = carts
    .map((cart) => {
      const badgeClass = `badge ${cart.status}`;
      return `
        <tr>
          <td>${cart.customerId}</td>
          <td>${cart.name || "—"}</td>
          <td><span class="${badgeClass}">${cart.statusDisplay}</span></td>
          <td>${cart.totalItems}</td>
          <td>${formatCurrency(cart.totalPrice)}</td>
          <td>${formatDate(cart.lastModified)}</td>
          <td>
            <button
              type="button"
              class="view-cart-btn"
              data-view-cart="${cart.customerId}"
              aria-label="View cart ${cart.customerId}"
            >
              View Cart
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
  
  // Bind click events for View Cart buttons
  bindTableActions();
};

const fetchJson = async (url, { method = "GET", body, headers = {} } = {}) => {
  const options = {
    method,
    headers: {
      Accept: "application/json",
      ...headers,
    },
  };
  if (body !== undefined) {
    options.body = typeof body === "string" ? body : JSON.stringify(body);
    options.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      console.error("Failed to parse JSON response", error, text);
    }
  }
  if (!response.ok) {
    const message =
      payload?.message || payload?.error || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
};

const apiRequest = (path = "", options) => fetchJson(`${API_BASE}${path}`, options);

const getFieldValue = (form, name) => {
  const field = form.elements.namedItem(name);
  if (!field) return "";
  return field.value.trim();
};

const refreshList = async (params) => {
  try {
    const query = params && params.toString() ? `?${params.toString()}` : "";
    const data = await apiRequest(query);
    if (!Array.isArray(data)) {
      console.error("Expected array but got:", data);
      tableBody.innerHTML =
        '<tr><td colspan="6" class="empty">No shopcarts found.</td></tr>';
      return;
    }
    const normalized = data.map((cart) => normalizeCart(cart));
    renderTable(normalized);
    clearAlert(); // Clear any previous errors on success
  } catch (error) {
    console.error("Error loading shopcarts:", error);
    const errorMessage = error.message || "An error occurred";
    // Check if it's an invalid filter error
    if (errorMessage.includes("Invalid status") || errorMessage.includes("Invalid filter")) {
      showAlert("Invalid filter option", "error");
    } else {
      showAlert(errorMessage, "error");
    }
    // Show empty state on error
    tableBody.innerHTML =
      '<tr><td colspan="6" class="empty">No shopcarts found.</td></tr>';
  }
};

const bindResultCardActions = (cart) => {
  if (!cart) return;
  const deleteButton = resultCard.querySelector("[data-delete-cart]");
  if (!deleteButton) return;
  deleteButton.addEventListener("click", () => handleResultDelete(cart.customerId));
};

const bindTableActions = () => {
  // Bind View Cart buttons in the table
  const viewButtons = tableBody.querySelectorAll("[data-view-cart]");
  viewButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const customerId = button.getAttribute("data-view-cart");
      viewCartById(Number(customerId));
    });
  });
};

const deleteShopcartRequest = (customerId) =>
  apiRequest(`/${customerId}`, { method: "DELETE" });

const handleDeleteError = (error) => {
  const message =
    error && /not found/i.test(error.message || "")
      ? "Cart not found"
      : error?.message || "Unable to delete the cart.";
  showAlert(message, "error");
};

const handleResultDelete = async (customerId) => {
  if (!customerId) return;
  const confirm = window.confirm(
    `Delete shopcart ${customerId}? This action cannot be undone.`
  );
  if (!confirm) {
    return;
  }
  try {
    await deleteShopcartRequest(customerId);
    renderShopcartCard(null);
    await refreshList();
    showAlert(`Shopcart ${customerId} deleted`, "success");
  } catch (error) {
    handleDeleteError(error);
  }
};

const handleCreate = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  if (!customerId) {
    showAlert("Customer ID is required", "error");
    return;
  }
  const cartName = getFieldValue(form, "cartName");
  const statusValue = getFieldValue(form, "status");
  const payload = { customer_id: customerId };
  if (statusValue) payload.status = statusValue;
  if (cartName) payload.name = cartName;
  try {
    const response = await apiRequest("", { method: "POST", body: payload });
    const cart = normalizeCart(response);
    renderShopcartCard(cart);
    showAlert("Shopcart created successfully", "success");
    form.reset();
    await refreshList();
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const handleUpdate = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const statusValue = getFieldValue(form, "status");
  if (!customerId || !statusValue) {
    showAlert("Customer ID and status are required", "error");
    return;
  }
  try {
    const response = await apiRequest(`/${customerId}`, {
      method: "PUT",
      body: { status: statusValue },
    });
    renderShopcartCard(normalizeCart(response));
    const statusLabel = formatStatusLabel(statusValue);
    showAlert(`Shopcart ${customerId} updated to ${statusLabel}`, "success");
    await refreshList();
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const viewCartById = async (customerId) => {
  if (!customerId) {
    showAlert("Invalid customer ID", "error");
    return;
  }
  try {
    const response = await apiRequest(`/${customerId}`);
    const cart = normalizeCart(response);
    renderShopcartCard(cart);
    showAlert(`Loaded shopcart ${customerId}`, "info");
    // Scroll to the result card
    resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    const message = error && /not found/i.test(error.message || "")
      ? "Cart not found"
      : error?.message || "Unable to load the cart.";
    showAlert(message, "error");
    renderShopcartCard(null);
  }
};

const handleRead = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  if (!customerId) {
    showAlert("Enter the customer ID you want to fetch", "error");
    return;
  }
  await viewCartById(customerId);
};

const handleDelete = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  if (!customerId) {
    showAlert("Enter the customer ID you want to delete", "error");
    return;
  }
  try {
    await deleteShopcartRequest(customerId);
    if (
      !resultCard.hidden &&
      resultCard.textContent.includes(String(customerId))
    ) {
      renderShopcartCard(null);
    }
    showAlert(`Shopcart ${customerId} deleted`, "success");
    form.reset();
    await refreshList();
  } catch (error) {
    handleDeleteError(error);
  }
};

const handleAction = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const action = getFieldValue(form, "action");
  if (!customerId || !action) {
    showAlert("Enter a customer ID and select an action", "error");
    return;
  }
  const endpoint = actionEndpoints[action];
  try {
    const response = await apiRequest(`/${customerId}/${endpoint}`, {
      method: "PATCH",
    });
    renderShopcartCard(normalizeCart(response));
    showAlert(`Action ${action} applied to shopcart ${customerId}`, "success");
    await refreshList();
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const handleQuery = async (event) => {
  event.preventDefault();
  const params = new URLSearchParams();
  const customerId = getFieldValue(queryForm, "customerId");
  let statusValue = getFieldValue(queryForm, "status");
  const minValue = getFieldValue(queryForm, "totalPriceGt");
  const maxValue = getFieldValue(queryForm, "totalPriceLt");
  if (customerId) params.set("customer_id", customerId);
  // Set status filter value
  if (statusValue) {
    params.set("status", statusValue);
  }
  if (minValue) params.set("total_price_gt", minValue);
  if (maxValue) params.set("total_price_lt", maxValue);
  await refreshList(params);
  showAlert("Query completed", "info");
};

const handleClearFilters = async () => {
  queryForm.reset();
  await refreshList();
  showAlert("Filters cleared. Showing all shopcarts.", "info");
};

const handleListFilter = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const statusValue = getFieldValue(form, "status");
  const params = new URLSearchParams();
  if (statusValue) {
    params.set("status", statusValue);
  }
  await refreshList(params);
  if (statusValue) {
    showAlert(`Filtered by status: ${statusValue}`, "info");
  } else {
    showAlert("Showing all shopcarts", "info");
  }
};

const handleListResetFilter = async () => {
  if (listFilterForm) {
    listFilterForm.reset();
  }
  await refreshList();
  showAlert("Filter reset - showing all shopcarts", "info");
};

// ---------------------------------------------------------------------------
// Item helpers
// ---------------------------------------------------------------------------
const renderItemsTable = (items) => {
  if (!itemTableBody) return;
  if (!Array.isArray(items) || items.length === 0) {
    itemTableBody.innerHTML =
      '<tr><td colspan="4" class="empty">No items to display.</td></tr>';
    return;
  }
  itemTableBody.innerHTML = items
    .map(
      (item) => `<tr>
        <td>${item.product_id ?? item.productId ?? "—"}</td>
        <td>${item.description ?? "—"}</td>
        <td>${item.quantity ?? 0}</td>
        <td>${formatCurrency(item.price)}</td>
      </tr>`
    )
    .join("");
};

const getItemPayload = (form, { requirePrice = false } = {}) => {
  const quantityRaw = getFieldValue(form, "quantity");
  const priceRaw = getFieldValue(form, "price");
  const descRaw = getFieldValue(form, "description");
  const payload = {};
  if (quantityRaw !== "") payload.quantity = Number(quantityRaw);
  if (priceRaw !== "") payload.price = Number(priceRaw);
  if (descRaw !== "") payload.description = descRaw;
  if (requirePrice && payload.price === undefined) {
    throw new Error("Price is required");
  }
  return payload;
};

const refreshCartAndItems = async (customerId) => {
  await viewCartById(customerId);
  try {
    const items = await apiRequest(`/${customerId}/items`);
    renderItemsTable(items);
  } catch (error) {
    console.error("Failed to refresh items", error);
  }
};

const handleItemAdd = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const productId = Number(getFieldValue(form, "productId"));
  if (!customerId || !productId) {
    showAlert("Customer ID and Product ID are required", "error");
    return;
  }
  try {
    const payload = getItemPayload(form, { requirePrice: true });
    payload.product_id = productId;
    await apiRequest(`/${customerId}/items`, { method: "POST", body: payload });
    showAlert(`Added product ${productId} to cart ${customerId}`, "success");
    form.reset();
    await refreshCartAndItems(customerId);
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const handleItemUpdate = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const productId = Number(getFieldValue(form, "productId"));
  if (!customerId || !productId) {
    showAlert("Customer ID and Product ID are required", "error");
    return;
  }
  try {
    const payload = getItemPayload(form);
    if (!Object.keys(payload).length) {
      showAlert("Provide at least one field to update", "error");
      return;
    }
    await apiRequest(`/${customerId}/items/${productId}`, {
      method: "PUT",
      body: payload,
    });
    showAlert(`Updated product ${productId} in cart ${customerId}`, "success");
    form.reset();
    await refreshCartAndItems(customerId);
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const handleItemDelete = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const productId = Number(getFieldValue(form, "productId"));
  if (!customerId || !productId) {
    showAlert("Customer ID and Product ID are required", "error");
    return;
  }
  try {
    await apiRequest(`/${customerId}/items/${productId}`, { method: "DELETE" });
    showAlert(`Deleted product ${productId} from cart ${customerId}`, "success");
    form.reset();
    await refreshCartAndItems(customerId);
  } catch (error) {
    showAlert(error.message, "error");
  }
};

const handleItemList = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  if (!customerId) {
    showAlert("Customer ID is required", "error");
    return;
  }
  try {
    const items = await apiRequest(`/${customerId}/items`);
    renderItemsTable(items);
    showAlert(`Listed items for cart ${customerId}`, "info");
  } catch (error) {
    showAlert(error.message, "error");
    renderItemsTable([]);
  }
};

const handleItemRead = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const customerId = Number(getFieldValue(form, "customerId"));
  const productId = Number(getFieldValue(form, "productId"));
  if (!customerId || !productId) {
    showAlert("Customer ID and Product ID are required", "error");
    return;
  }
  try {
    const item = await apiRequest(`/${customerId}/items/${productId}`);
    renderItemsTable([item]);
    showAlert(`Fetched item ${productId} for cart ${customerId}`, "info");
  } catch (error) {
    showAlert(error.message, "error");
    renderItemsTable([]);
  }
};

const bindItemForms = () => {
  if (itemForms.add) itemForms.add.addEventListener("submit", handleItemAdd);
  if (itemForms.update)
    itemForms.update.addEventListener("submit", handleItemUpdate);
  if (itemForms.delete)
    itemForms.delete.addEventListener("submit", handleItemDelete);
  if (itemForms.list) itemForms.list.addEventListener("submit", handleItemList);
  if (itemForms.read) itemForms.read.addEventListener("submit", handleItemRead);
};

forms.create.addEventListener("submit", handleCreate);
forms.update.addEventListener("submit", handleUpdate);
forms.read.addEventListener("submit", handleRead);
forms.delete.addEventListener("submit", handleDelete);
forms.action.addEventListener("submit", handleAction);
queryForm.addEventListener("submit", handleQuery);
if (clearFiltersBtn) {
  clearFiltersBtn.addEventListener("click", handleClearFilters);
}

if (listFilterForm) {
  listFilterForm.addEventListener("submit", handleListFilter);
}
if (listResetFilterBtn) {
  listResetFilterBtn.addEventListener("click", handleListResetFilter);
}

bindItemForms();
clearAlert();
refreshList();
