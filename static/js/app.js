// Shopping Cart and Wishlist Management
// Wait for currency manager to be ready
let currencyReady = false;

class SafeCart {
  constructor() {
    this.cart = this.getStoredData("cart") || [];
    this.wishlist = this.getStoredData("wishlist") || [];
    this.waitForCurrency().then(() => this.init());
  }

  async waitForCurrency() {
    // Wait for currency manager to initialize
    while (typeof currencyManager === "undefined") {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    currencyReady = true;
  }

  init() {
    this.updateCounters();
    this.setupEventListeners();
    this.renderCartItems();
    this.renderWishlistItems();
  }

  // Local Storage Methods
  getStoredData(key) {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error(`Error getting stored data for ${key}:`, error);
      return null;
    }
  }

  setStoredData(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
      console.error(`Error storing data for ${key}:`, error);
    }
  }

  // Cart Methods
  addToCart(id, name, price, image) {
    const existingItem = this.cart.find((item) => item.id === id);

    if (existingItem) {
      existingItem.quantity += 1;
    } else {
      this.cart.push({
        id,
        name,
        price,
        image,
        quantity: 1,
      });
    }

    this.setStoredData("cart", this.cart);
    this.updateCounters();
    this.renderCartItems();
    this.showNotification(`${name} added to cart!`, "success");
  }

  removeFromCart(id) {
    const itemIndex = this.cart.findIndex((item) => item.id === id);
    if (itemIndex > -1) {
      const removedItem = this.cart[itemIndex];
      this.cart.splice(itemIndex, 1);
      this.setStoredData("cart", this.cart);
      this.updateCounters();
      this.renderCartItems();
      this.showNotification(`${removedItem.name} removed from cart!`, "info");
    }
  }

  updateQuantity(id, quantity) {
    const item = this.cart.find((item) => item.id === id);
    if (item) {
      if (quantity <= 0) {
        this.removeFromCart(id);
      } else {
        item.quantity = quantity;
        this.setStoredData("cart", this.cart);
        this.updateCounters();
        this.renderCartItems();
      }
    }
  }

  getCartTotal() {
    return this.cart.reduce(
      (total, item) => total + item.price * item.quantity,
      0
    );
  }

  // Wishlist Methods
  addToWishlist(id, name, price, image) {
    const existingItem = this.wishlist.find((item) => item.id === id);

    if (!existingItem) {
      this.wishlist.push({
        id,
        name,
        price,
        image,
      });

      this.setStoredData("wishlist", this.wishlist);
      this.updateCounters();
      this.renderWishlistItems();
      this.showNotification(`${name} added to wishlist!`, "success");
    } else {
      this.showNotification(`${name} is already in your wishlist!`, "info");
    }
  }

  removeFromWishlist(id) {
    const itemIndex = this.wishlist.findIndex((item) => item.id === id);
    if (itemIndex > -1) {
      const removedItem = this.wishlist[itemIndex];
      this.wishlist.splice(itemIndex, 1);
      this.setStoredData("wishlist", this.wishlist);
      this.updateCounters();
      this.renderWishlistItems();
      this.showNotification(
        `${removedItem.name} removed from wishlist!`,
        "info"
      );
    }
  }

  moveToCart(id) {
    const item = this.wishlist.find((item) => item.id === id);
    if (item) {
      this.addToCart(item.id, item.name, item.price, item.image);
      this.removeFromWishlist(id);
    }
  }

  // UI Methods
  updateCounters() {
    const cartCount = this.cart.reduce(
      (total, item) => total + item.quantity,
      0
    );
    const wishlistCount = this.wishlist.length;

    const cartCountElements = document.querySelectorAll("#cart-count");
    const wishlistCountElements = document.querySelectorAll("#wishlist-count");

    if (cartCountElements.length) {
      cartCountElements.forEach((element) => {
        element.textContent = cartCount;
      });
    }

    if (wishlistCountElements.length) {
      wishlistCountElements.forEach((element) => {
        element.textContent = wishlistCount;
      });
    }
  }

  renderCartItems() {
    const cartItemsContainer = document.getElementById("cart-items");
    if (!cartItemsContainer) return;

    if (this.cart.length === 0) {
      cartItemsContainer.innerHTML = `
                <div class="empty-state">
                    <h3>Your cart is empty</h3>
                    <p>Start shopping to add items to your cart</p>
                    <a href="home">Continue Shopping</a>
                </div>
            `;
      this.updateCartSummary();
      return;
    }

    cartItemsContainer.innerHTML = this.cart
      .map(
        (item) => `
            <div class="cart-item">
                <div class="cart-item-image">
                    <img src="${item.image}" alt="${item.name}">
                </div>
                <div class="cart-item-details">
                    <h4>${item.name}</h4>
                    <p>Quantity: ${item.quantity}</p>
                </div>
                <div class="cart-item-price">${
                  currencyReady && typeof currencyManager !== "undefined"
                    ? currencyManager.formatPrice(item.price * item.quantity)
                    : "$" + (item.price * item.quantity).toFixed(2)
                }</div>
                <button class="btn btn-remove" onclick="safeCart.removeFromCart('${
                  item.id
                }')">Remove</button>
            </div>
        `
      )
      .join("");

    this.updateCartSummary();
  }

  renderWishlistItems() {
    const wishlistItemsContainer = document.getElementById("wishlist-items");
    if (!wishlistItemsContainer) return;

    if (this.wishlist.length === 0) {
      wishlistItemsContainer.innerHTML = `
                <div class="empty-state">
                    <h3>Your wishlist is empty</h3>
                    <p>Add items you love to your wishlist</p>
                    <a href="home">Continue Shopping</a>
                </div>
            `;
      return;
    }

    wishlistItemsContainer.innerHTML = this.wishlist
      .map(
        (item) => `
            <div class="wishlist-item">
                <div class="wishlist-item-image">
                    <img src="${item.image}" alt="${item.name}">
                </div>
                <div class="wishlist-item-details">
                    <h4>${item.name}</h4>
                    <p>${
                      currencyReady && typeof currencyManager !== "undefined"
                        ? currencyManager.formatPrice(item.price)
                        : "$" + item.price.toFixed(2)
                    }</p>
                    <div class="wishlist-item-actions">
                        <button class="btn btn-cart" onclick="safeCart.moveToCart('${
                          item.id
                        }')">Add to Cart</button>
                        <button class="btn btn-remove" onclick="safeCart.removeFromWishlist('${
                          item.id
                        }')">Remove</button>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  updateCartSummary() {
    const subtotal = this.getCartTotal();
    const shipping = subtotal > 0 ? 9.99 : 0;
    const tax = subtotal * 0.08; // 8% tax
    const total = subtotal + shipping + tax;

    const subtotalElement = document.getElementById("subtotal");
    const taxElement = document.getElementById("tax");
    const totalElement = document.getElementById("total");

    if (currencyReady && typeof currencyManager !== "undefined") {
      if (subtotalElement)
        subtotalElement.textContent = currencyManager.formatPrice(subtotal);
      if (taxElement) taxElement.textContent = currencyManager.formatPrice(tax);
      if (totalElement)
        totalElement.textContent = currencyManager.formatPrice(total);
    } else {
      // Fallback to USD formatting
      if (subtotalElement)
        subtotalElement.textContent = `$${subtotal.toFixed(2)}`;
      if (taxElement) taxElement.textContent = `$${tax.toFixed(2)}`;
      if (totalElement) totalElement.textContent = `$${total.toFixed(2)}`;
    }
  }

  showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.innerHTML = `
            <div class="notification-content">
                <span>${message}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

    // Add notification styles if not already present
    if (!document.querySelector("#notification-styles")) {
      const styles = document.createElement("style");
      styles.id = "notification-styles";
      styles.textContent = `
                .notification {
                    position: fixed;
                    top: 100px;
                    right: 20px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                    z-index: 1001;
                    animation: slideInRight 0.3s ease;
                    max-width: 300px;
                }
                .notification.success {
                    border-left: 4px solid #10b981;
                }
                .notification.info {
                    border-left: 4px solid #3b82f6;
                }
                .notification.error {
                    border-left: 4px solid #ef4444;
                }
                .notification-content {
                    padding: 1rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .notification-close {
                    background: none;
                    border: none;
                    font-size: 1.2rem;
                    cursor: pointer;
                    color: #64748b;
                }
                @keyframes slideInRight {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
      document.head.appendChild(styles);
    }

    // Add to page
    document.body.appendChild(notification);

    // Auto remove after 3 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 3000);
  }

  checkout() {
    if (this.cart.length === 0) {
      this.showNotification("Your cart is empty!", "error");
      return;
    }

    const total = this.getCartTotal() + 9.99 + this.getCartTotal() * 0.08;
    const formattedTotal =
      currencyReady && typeof currencyManager !== "undefined"
        ? currencyManager.formatPrice(total)
        : `$${total.toFixed(2)}`;
    this.showNotification(
      `Checkout successful! Total: ${formattedTotal}`,
      "success"
    );

    // Clear cart after checkout
    this.cart = [];
    this.setStoredData("cart", this.cart);
    this.updateCounters();
    this.renderCartItems();
  }

  setupEventListeners() {
    // Handle page load
    document.addEventListener("DOMContentLoaded", () => {
      this.updateCounters();
      this.renderCartItems();
      this.renderWishlistItems();
    });
  }
}

// Initialize the SafeCart system
const safeCart = new SafeCart();

// Global functions for onclick handlers
function isAuthenticated() {
  return !!localStorage.getItem("user");
}

function requireAuth(action) {
  if (!isAuthenticated()) {
    alert("Please login to use this feature.");
    window.location.href = "login";
    return false;
  }
  return true;
}

function addToCart(id, name, price, image) {
  if (!requireAuth()) return;
  safeCart.addToCart(id, name, price, image);
}

function addToWishlist(id, name, price, image) {
  if (!requireAuth()) return;
  safeCart.addToWishlist(id, name, price, image);
}

function removeFromCart(id) {
  safeCart.removeFromCart(id);
}

function removeFromWishlist(id) {
  safeCart.removeFromWishlist(id);
}

function moveToCart(id) {
  safeCart.moveToCart(id);
}

function checkout() {
  if (!requireAuth()) return;
  // Step 1: Hide cart summary, show address form
  document.querySelector(".cart-summary").style.display = "none";
  document.getElementById("address-form-step").style.display = "block";
  document.getElementById("payment-method-step").style.display = "none";
  document.getElementById("qr-step").style.display = "none";
}

// Address form submit handler
const addressForm = document.getElementById("address-form");
if (addressForm) {
  addressForm.addEventListener("submit", function (event) {
    event.preventDefault();
    document.getElementById("address-form-step").style.display = "none";
    document.getElementById("payment-method-step").style.display = "block";
    document.getElementById("qr-step").style.display = "none";
  });
}

// Payment method form handler
const paymentMethodForm = document.getElementById("payment-method-form");
const codStep = document.getElementById("cod-step");
const codMobileForm = document.getElementById("cod-mobile-form");
const codOtpForm = document.getElementById("cod-otp-form");
const codOtpMessage = document.getElementById("cod-otp-message");
let generatedOtp = null;

if (paymentMethodForm) {
  paymentMethodForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const method = paymentMethodForm.elements["payment-method"].value;
    document.getElementById("payment-method-step").style.display = "none";
    if (method === "upi") {
      document.getElementById("qr-step").style.display = "block";
      document.getElementById("payment-complete-btn").style.display = "none";
      setTimeout(function () {
        document.getElementById("payment-complete-btn").style.display =
          "inline-block";
      }, 3000);
      codStep && (codStep.style.display = "none");
    } else if (method === "cod") {
      codStep && (codStep.style.display = "block");
      document.getElementById("qr-step").style.display = "none";
    }
  });
}

if (codMobileForm) {
  codMobileForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const mobile = document.getElementById("cod-mobile").value;
    if (!/^\d{10}$/.test(mobile)) {
      codOtpMessage.textContent =
        "Please enter a valid 10-digit mobile number.";
      return;
    }
    // Generate random 6-digit OTP
    generatedOtp = Math.floor(100000 + Math.random() * 900000).toString();
    codOtpMessage.textContent = `OTP sent to ${mobile}. (Demo OTP: ${generatedOtp})`;
    codMobileForm.style.display = "none";
    codOtpForm.style.display = "block";
  });
}

if (codOtpForm) {
  codOtpForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const enteredOtp = document.getElementById("cod-otp").value;
    if (enteredOtp === generatedOtp) {
      codOtpMessage.textContent = "";
      codStep.style.display = "none";
      document.getElementById("qr-step").innerHTML =
        "<h3>Thank you for your purchase!</h3><p>Your order has been confirmed and will be shipped soon.</p>";
      document.getElementById("qr-step").style.display = "block";
      // Save order to localStorage with a placement date within 5 days
      if (safeCart.cart && safeCart.cart.length > 0) {
        const orders = JSON.parse(localStorage.getItem("orders") || "[]");
        const now = new Date();
        const maxDays = 5;
        const randomDays = Math.floor(Math.random() * maxDays);
        const orderDate = new Date(
          now.getTime() + randomDays * 24 * 60 * 60 * 1000
        );
        const order = {
          id: "ORD" + Date.now(),
          items: safeCart.cart.map((item) => ({ ...item })),
          date: orderDate.toISOString(),
        };
        orders.unshift(order);
        localStorage.setItem("orders", JSON.stringify(orders));
      }
      safeCart.cart = [];
      safeCart.setStoredData("cart", safeCart.cart);
      safeCart.updateCounters();
      safeCart.renderCartItems();
    } else {
      codOtpMessage.textContent = "Invalid OTP. Please try again.";
    }
  });
}

// Payment complete button handler
const paymentBtn = document.getElementById("payment-complete-btn");
if (paymentBtn) {
  paymentBtn.addEventListener("click", function () {
    document.getElementById("qr-step").innerHTML =
      "<h3>Thank you for your purchase!</h3><p>Your payment has been received. Your order will be shipped soon.</p>";
    if (safeCart.cart && safeCart.cart.length > 0) {
      const orders = JSON.parse(localStorage.getItem("orders") || "[]");
      const now = new Date();
      const maxDays = 5;
      const randomDays = Math.floor(Math.random() * maxDays);
      const orderDate = new Date(
        now.getTime() + randomDays * 24 * 60 * 60 * 1000
      );
      const order = {
        id: "ORD" + Date.now(),
        items: safeCart.cart.map((item) => ({ ...item })),
        date: orderDate.toISOString(),
      };
      orders.unshift(order);
      localStorage.setItem("orders", JSON.stringify(orders));
    }
    safeCart.cart = [];
    safeCart.setStoredData("cart", safeCart.cart);
    safeCart.updateCounters();
    safeCart.renderCartItems();
  });
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  // Initialize SafeCart after a short delay to ensure currency manager is ready
  setTimeout(() => {
    if (typeof safeCart !== "undefined") {
      safeCart.init();
    }
  }, 500);
});

// Handle smooth scrolling for internal links
document.addEventListener("DOMContentLoaded", () => {
  const links = document.querySelectorAll('a[href^="#"]');
  links.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = link.getAttribute("href").substring(1);
      const targetElement = document.getElementById(targetId);
      if (targetElement) {
        targetElement.scrollIntoView({ behavior: "smooth" });
      }
    });
  });
});

// Handle responsive navigation
document.addEventListener("DOMContentLoaded", () => {
  const navToggle = document.querySelector(".nav-toggle");
  const navMenu = document.querySelector(".nav-menu");

  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      navMenu.classList.toggle("active");
    });
  }
});

// Add loading states for better UX
function showLoading(element) {
  element.classList.add("loading");
  element.style.pointerEvents = "none";
}

function hideLoading(element) {
  element.classList.remove("loading");
  element.style.pointerEvents = "auto";
}

// Search functionality (for future enhancement)
function searchProducts(query) {
  const products = document.querySelectorAll(".product-card");
  products.forEach((product) => {
    const name = product.querySelector("h3").textContent.toLowerCase();
    const isVisible = name.includes(query.toLowerCase());
    product.style.display = isVisible ? "block" : "none";
  });
}

// Filter products by price range (for future enhancement)
function filterByPrice(min, max) {
  const products = document.querySelectorAll(".product-card");
  products.forEach((product) => {
    const priceText = product.querySelector(".price").textContent;
    const price = parseFloat(priceText.replace("$", ""));
    const isInRange = price >= min && price <= max;
    product.style.display = isInRange ? "block" : "none";
  });
}

// Image lazy loading for better performance
document.addEventListener("DOMContentLoaded", () => {
  const images = document.querySelectorAll("img[data-src]");
  const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.classList.remove("lazy");
        observer.unobserve(img);
      }
    });
  });

  images.forEach((img) => imageObserver.observe(img));
});

// Handle form submissions (for future enhancement)
function handleFormSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  // Add your form handling logic here
  console.log("Form submitted:", Object.fromEntries(formData));
}

// Keyboard navigation support
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    // Close modals, dropdowns, etc.
    const modals = document.querySelectorAll(".modal.active");
    modals.forEach((modal) => modal.classList.remove("active"));
  }
});

// Handle offline functionality
window.addEventListener("online", () => {
  safeCart.showNotification("You are back online!", "success");
});

window.addEventListener("offline", () => {
  safeCart.showNotification(
    "You are offline. Some features may not work.",
    "info"
  );
});

// Performance optimization: Debounce function
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Add to favorites with local storage persistence
function addToFavorites(id, name, price, image) {
  let favorites = JSON.parse(localStorage.getItem("favorites") || "[]");

  if (!favorites.find((item) => item.id === id)) {
    favorites.push({ id, name, price, image });
    localStorage.setItem("favorites", JSON.stringify(favorites));
    safeCart.showNotification(`${name} added to favorites!`, "success");
  } else {
    safeCart.showNotification(`${name} is already in favorites!`, "info");
  }
}

// Export functions for testing (if needed)
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    SafeCart,
    addToCart,
    addToWishlist,
    removeFromCart,
    removeFromWishlist,
    checkout,
  };
}

function updateAuthLinks() {
  const userLinks = document.getElementById("user-auth-links");
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (user && user.email) {
    userLinks.innerHTML = `<button id="logout-btn" class="btn btn-remove" style="margin-left:8px;">Logout</button>`;
    setTimeout(() => {
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) {
        logoutBtn.onclick = function () {
          localStorage.removeItem("user");
          window.location.reload();
        };
      }
    }, 0);
  } else {
    userLinks.innerHTML = `<a href="login" class="nav-link">Login</a> / <a href="signup" class="nav-link">Sign Up</a>`;
  }
}
document.addEventListener("DOMContentLoaded", updateAuthLinks);

function updateProfilePhoto() {
  const profileImg = document.querySelector(".profile-avatar-img");
  if (profileImg) {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    const savedPhoto = localStorage.getItem("profilePhoto");

    // Show custom photo only if user is logged in and has uploaded a photo
    if (user && user.email && savedPhoto) {
      profileImg.src = savedPhoto;
    } else {
      // Show default avatar for non-logged in users or users without custom photo
      profileImg.src = "images/default-avatar.jpg";
    }
  }
}

function updateProfileDropdown() {
  const profileBtn = document.getElementById("profile-btn");
  const profileDropdown = document.getElementById("profile-dropdown");
  const profileContent = document.getElementById("profile-dropdown-content");
  const profileMenu = document.getElementById("profile-menu");
  if (!profileBtn || !profileDropdown || !profileContent || !profileMenu)
    return;
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (user && user.email) {
    profileContent.innerHTML = `<h4>Email</h4><p>${user.email}</p><button id='logout-btn' class='btn btn-remove btn-block'>Logout</button>`;
  } else {
    profileContent.innerHTML = `<a href='login' class='btn btn-primary btn-block' style='margin-bottom:0.5rem;'>Login</a><a href='signup' class='btn btn-primary btn-block'>Sign Up</a>`;
  }
  // Remove previous event listeners
  profileBtn.onclick = null;
  // Toggle dropdown
  profileBtn.onclick = function (e) {
    e.stopPropagation();
    profileMenu.classList.toggle("open");
  };
  // Logout logic
  setTimeout(() => {
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
      logoutBtn.onclick = function () {
        localStorage.removeItem("user");
        localStorage.removeItem("profilePhoto"); // Remove custom photo on logout
        window.location.reload();
      };
    }
  }, 0);
  // Prevent duplicate outside click listeners
  if (!window._profileDropdownListener) {
    document.addEventListener("click", function (e) {
      if (!profileMenu.contains(e.target)) {
        profileMenu.classList.remove("open");
      }
    });
    window._profileDropdownListener = true;
  }
}
document.addEventListener("DOMContentLoaded", updateProfileDropdown);
document.addEventListener("DOMContentLoaded", updateProfilePhoto);

// Utility function to clear all data (can be called from browser console)
function clearAllData() {
  localStorage.clear();
  alert("All data cleared! Page will reload.");
  window.location.reload();
}

// Make it available globally
window.clearAllData = clearAllData;
