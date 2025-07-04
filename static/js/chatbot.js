class ChatBot {
    constructor() {
        this.isOpen = false;
        this.isTyping = false;
        this.messageCount = 0;
        this.apiKey = 'nawabkhan';
        this.baseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
        this.sessionId = this.generateSessionId();
        this.awaitingPhone = false;
        this.awaitingOTP = false;
        this.lastUserMessage = '';
        this.phoneNumber = '';

        this.initializeElements();
        this.bindEvents();
        this.showWelcomeMessage();
    }

    generateSessionId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    initializeElements() {
        this.chatToggle = document.getElementById('chatToggle');
        this.chatContainer = document.getElementById('chatContainer');
        this.chatOverlay = document.getElementById('chatOverlay');
        this.minimizeChat = document.getElementById('minimizeChat');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.chatMessages = document.getElementById('chatMessages');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.notificationBadge = document.getElementById('notificationBadge');
        this.quickActionBtns = document.querySelectorAll('.quick-action-btn');
        this.quickActionsContainer = document.getElementById('quickActions');
    }

    bindEvents() {
        this.chatToggle.addEventListener('click', () => this.toggleChat());
        this.minimizeChat.addEventListener('click', () => this.closeChat());
        this.chatOverlay.addEventListener('click', () => this.closeChat());
        this.sendBtn.addEventListener('click', e => {
            e.preventDefault();
            this.sendMessage();
        });
        this.messageInput.addEventListener('keypress', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.quickActionBtns.forEach(btn =>
            btn.addEventListener('click', () => this.handleQuickAction(btn.dataset.category))
        );
        this.messageInput.addEventListener('input', () => this.autoResizeInput());
        this.chatContainer.addEventListener('click', e => e.stopPropagation());
    }

    toggleChat() {
        this.isOpen ? this.closeChat() : this.openChat();
    }

    openChat() {
        this.isOpen = true;
        this.chatContainer.classList.add('active');
        this.chatOverlay.classList.add('active');
        this.chatToggle.classList.add('active');
        this.hideNotificationBadge();
        this.messageInput.focus();
        document.body.style.overflow = 'hidden';
    }

    closeChat() {
        this.isOpen = false;
        this.chatContainer.classList.remove('active');
        this.chatOverlay.classList.remove('active');
        this.chatToggle.classList.remove('active');
        document.body.style.overflow = '';
    }

    // NEW: hide quick-action buttons container
    hideQuickActions() {
        if (this.quickActionsContainer) {
            this.quickActionsContainer.style.display = 'none';
        }
    }

    sendMessage() {
        const msg = this.messageInput.value.trim();
        if (!msg) return;
        this.hideQuickActions();
        this.addMessage(msg, 'user');
        this.messageInput.value = '';
        this.autoResizeInput();
        this.showTypingIndicator();

        if (this.awaitingPhone) {
            this.awaitingPhone = false;
            this.phoneNumber = msg;
            this.sendOTP(msg);
            return;
        }
        if (this.awaitingOTP) {
            this.awaitingOTP = false;
            this.verifyOTP(this.phoneNumber, msg);
            return;
        }

        this.lastUserMessage = msg;
        this.generateBotResponse(msg);
    }

    addMessage(content, sender = 'bot') {
        const div = document.createElement('div');
        div.className = `message ${sender}-message fade-in`;
        const time = this.getCurrentTime();
        const avatar = sender === 'bot' ? 'fas fa-robot' : 'fas fa-user';
        div.innerHTML = `
            <div class="message-avatar"><i class="${avatar}"></i></div>
            <div class="message-content">
              <div class="message-bubble"><p>${content}</p></div>
              <small class="message-time">${time}</small>
            </div>`;
        this.chatMessages.appendChild(div);
        this.scrollToBottom();
        this.messageCount++;
    }

    addProductCard(product) {
        const card = document.createElement('div');
        card.className = 'product-card fade-in';
        const words = product.name.split(' ');
        const name = words.length > 6 ? words.slice(0, 6).join(' ') + '...' : product.name;
        card.innerHTML = `
            <div class="card mb-2 shadow-sm border">
              <div class="row g-0">
                <div class="col-4 product-image">
                  <img src="${product.image || product.first_image || ''}" alt="${product.name}" class="img-fluid rounded-start" onerror="this.style.display='none'" />
                </div>
                <div class="col-8">
                  <div class="card-body p-2">
                    <p class="card-title mb-1">${name}</p>
                    <p class="card-text mb-1 fw-bold">${product.price}</p>
                    ${product.features?.length ? `<ul class="product-features mb-2">${product.features.map(f => `<li>${f}</li>`).join('')}</ul>` : ''}
                    <a href="${product.link}" target="_blank" class="btn btn-sm btn-outline-primary">View</a>
                  </div>
                </div>
              </div>
            </div>`;
        this.chatMessages.appendChild(card);
        this.scrollToBottom();
    }

    // addOrderCard(order) {
    //     const card = document.createElement('div');
    //     card.className = 'order-card fade-in';
    //     card.innerHTML = `
    //         <div class="card mb-2 shadow-sm border">
    //           <div class="card-body p-2">
    //             <h6 class="card-title">Order #${order.order_id}</h6>
    //             <p class="card-text mb-1"><strong>Product:</strong> ${order.product_name}</p>
    //             <p class="card-text mb-1"><strong>Status:</strong> ${order.status}</p>
    //             ${order.order_date ? `<p class="card-text mb-1"><strong>Date:</strong> ${order.order_date}</p>` : ''}
    //           </div>
    //         </div>`;
    //     this.chatMessages.appendChild(card);
    //     this.scrollToBottom();
    // }
    addOrderCard(order) {
        const card = document.createElement('div');
        card.className = 'order-card fade-in';
    
        const imageUrl = order.product_image || '';  // Fallback if image is missing
        const productName = order.product_name || 'Product';
    
        card.innerHTML = `
            <div class="card mb-2 shadow-sm border">
                <div class="row g-0">
                    <div class="col-4 product-image">
                        <img src="${imageUrl}" alt="${productName}" class="img-fluid rounded-start" onerror="this.style.display='none'" />
                    </div>
                    <div class="col-8">
                        <div class="card-body p-2">
                            <h6 class="card-title mb-1 text-truncate">${productName}</h6>
                            <p class="card-text mb-1"><strong>Order ID:</strong> ${order.order_id}</p>
                            <p class="card-text mb-1"><strong>Status:</strong> ${order.status}</p>
                            ${order.order_date ? `<p class="card-text mb-1"><strong>Date:</strong> ${order.order_date}</p>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    
        this.chatMessages.appendChild(card);
        this.scrollToBottom();
    }
    

    generateBotResponse(userMessage) {
        this.showTypingIndicator();

        fetch(`${this.baseUrl}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': this.apiKey,
                'Accept': 'application/json'
            },
            body: JSON.stringify({ message: userMessage, session_id: this.sessionId })
        })
        .then(async res => {
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Status ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            this.hideTypingIndicator();
            if (data.response) data = data.response;

            if (data.status === "success" && data.data) {
                const { answer, orders, products, comparison, end } = data.data;
                if (answer) this.addMessage(answer, 'bot');
                if (orders && Array.isArray(orders)) orders.forEach(o => this.addOrderCard(o));
                if (products && Array.isArray(products)) products.forEach(p => this.addProductCard(p));
                if (comparison && Array.isArray(comparison)) {
                    comparison.forEach(item => {
                        /* your existing comparison rendering logic */
                    });
                }
                if (end) this.addMessage(end, 'bot');
            } else if (data.status === "error") {
                this.addMessage(data.data?.answer || "Sorry, an error occurred.", 'bot');
            } else {
                this.addMessage(data.data?.answer || "Sorry, I didn't get that.", 'bot');
            }
        })
        .catch(err => {
            console.error("API error:", err);
            this.hideTypingIndicator();
            this.addMessage(`Oops, something went wrong: ${err.message}`, 'bot');
        });
    }


    showTypingIndicator() {
        this.isTyping = true;
        this.typingIndicator.classList.add('active');
        this.scrollToBottom();
    }
    hideTypingIndicator() {
        this.isTyping = false;
        this.typingIndicator.classList.remove('active');
    }
    showWelcomeMessage() {
        setTimeout(() => this.showNotificationBadge(), 2000);
    }
    showNotificationBadge() {
        this.notificationBadge.style.display = 'flex';
        this.notificationBadge.textContent = '1';
    }
    hideNotificationBadge() {
        this.notificationBadge.style.display = 'none';
    }
    autoResizeInput() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }
    scrollToBottom() {
        setTimeout(() => this.chatMessages.scrollTop = this.chatMessages.scrollHeight, 100);
    }
    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
}

// Initialize chatbot
document.addEventListener('DOMContentLoaded', () => {
    window.chatBot = new ChatBot();
});
