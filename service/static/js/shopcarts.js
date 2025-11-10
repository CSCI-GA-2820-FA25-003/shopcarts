const API_BASE = "/shopcarts";
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
const listAllBtn = document.querySelector("#list-all");
const queryForm = document.querySelector("#query-form");

const forms = {
  create: document.querySelector("#create-form"),
  update: document.querySelector("#update-form"),
  read: document.querySelector("#read-form"),
  delete: document.querySelector("#delete-form"),
  action: document.querySelector("#action-form"),
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
    status: raw.status ?? "active",
    totalItems: snake ? raw.total_items ?? items.length : raw.totalItems ?? 0,
    totalPrice: raw.total_price ?? raw.totalPrice ?? computeTotals(),
    createdDate: snake ? raw.created_date : raw.createdDate,
    lastModified: snake ? raw.last_modified : raw.lastModified,
    items,
  };
};

const renderShopcartCard = (cart) => {
  if (!cart) {
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
    <p><span class="${badgeClass}">${cart.status}</span></p>
    <div class="metadata">
      <div><span>Total Items</span>${cart.totalItems}</div>
      <div><span>Total Price</span>${formatCurrency(cart.totalPrice)}</div>
      <div><span>Created</span>${formatDate(cart.createdDate)}</div>
      <div><span>Updated</span>${formatDate(cart.lastModified)}</div>
    </div>
    <div class="items">${itemsHtml}</div>
  `;
};

const renderTable = (carts) => {
  if (!Array.isArray(carts) || carts.length === 0) {
    tableBody.innerHTML =
      '<tr><td colspan="5" class="empty">No results match your filters.</td></tr>';
    return;
  }

  tableBody.innerHTML = carts
    .map((cart) => {
      const badgeClass = `badge ${cart.status}`;
      return `
        <tr>
          <td>${cart.customerId}</td>
          <td><span class="${badgeClass}">${cart.status}</span></td>
          <td>${cart.totalItems}</td>
          <td>${formatCurrency(cart.totalPrice)}</td>
          <td>${formatDate(cart.lastModified)}</td>
        </tr>
      `;
    })
    .join("");
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
    const normalized = data.map((cart) => normalizeCart(cart));
    renderTable(normalized);
  } catch (error) {
    showAlert(error.message, "error");
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
  const statusValue = getFieldValue(form, "status");
  const payload = { customer_id: customerId };
  if (statusValue) payload.status = statusValue;
  try {
    const response = await apiRequest("", { method: "POST", body: payload });
    const cart = normalizeCart(response);
    renderShopcartCard(cart);
    showAlert(`Shopcart ${customerId} created successfully`, "success");
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
    showAlert(`Shopcart ${customerId} updated to ${statusValue}`, "success");
    await refreshList();
  } catch (error) {
    showAlert(error.message, "error");
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
  try {
    const response = await apiRequest(`/${customerId}`);
    renderShopcartCard(normalizeCart(response));
    showAlert(`Loaded shopcart ${customerId}`, "info");
  } catch (error) {
    showAlert(error.message, "error");
  }
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
    await apiRequest(`/${customerId}`, { method: "DELETE" });
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
    showAlert(error.message, "error");
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
  const statusValue = getFieldValue(queryForm, "status");
  const minValue = getFieldValue(queryForm, "totalPriceGt");
  const maxValue = getFieldValue(queryForm, "totalPriceLt");
  if (customerId) params.set("customer_id", customerId);
  if (statusValue) params.set("status", statusValue);
  if (minValue) params.set("total_price_gt", minValue);
  if (maxValue) params.set("total_price_lt", maxValue);
  await refreshList(params);
  showAlert("Query completed", "info");
};

const handleListAll = async () => {
  queryForm.reset();
  await refreshList();
  showAlert("Listing all shopcarts", "info");
};

forms.create.addEventListener("submit", handleCreate);
forms.update.addEventListener("submit", handleUpdate);
forms.read.addEventListener("submit", handleRead);
forms.delete.addEventListener("submit", handleDelete);
forms.action.addEventListener("submit", handleAction);
queryForm.addEventListener("submit", handleQuery);
listAllBtn.addEventListener("click", handleListAll);

clearAlert();
refreshList();
