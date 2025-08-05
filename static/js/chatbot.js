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

        // Speech functionality
        this.speechRecognition = null;
        this.speechSynthesis = window.speechSynthesis;
        this.isListening = false;
        this.speechEnabled = true;
        this.currentUtterance = null;

        this.initializeSpeech();
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

    initializeSpeech() {
        // Check if Speech Recognition is supported
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.speechRecognition = new SpeechRecognition();
            
            this.speechRecognition.continuous = false;
            this.speechRecognition.interimResults = false;
            this.speechRecognition.lang = 'en-US';
            
            this.speechRecognition.onstart = () => {
                this.isListening = true;
                this.updateSpeechButton();
                this.showSpeechStatus('Listening...');
            };
            
            this.speechRecognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.messageInput.value = transcript;
                this.hideSpeechStatus();
                
                // Auto-send the message after speech recognition
                setTimeout(() => {
                    this.sendMessage();
                }, 500);
            };
            
            this.speechRecognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.isListening = false;
                this.updateSpeechButton();
                this.hideSpeechStatus();
                
                let errorMessage = 'Speech recognition error';
                switch(event.error) {
                    case 'no-speech':
                        errorMessage = 'No speech detected. Please try again.';
                        break;
                    case 'network':
                        errorMessage = 'Network error. Please check your connection.';
                        break;
                    case 'not-allowed':
                        if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
                            errorMessage = 'Microphone access requires HTTPS. Please use a secure connection.';
                        } else {
                            errorMessage = 'Microphone access denied. Please click the microphone icon in your browser\'s address bar and allow microphone access.';
                        }
                        break;
                    case 'service-not-allowed':
                        errorMessage = 'Speech service not allowed. Please enable microphone permissions for this site.';
                        break;
                }
                this.showSpeechStatus(errorMessage, true);
            };
            
            this.speechRecognition.onend = () => {
                this.isListening = false;
                this.updateSpeechButton();
                this.hideSpeechStatus();
            };
        } else {
            console.warn('Speech Recognition not supported in this browser');
        }

        // Ensure voices are loaded for speech synthesis
        if (this.speechSynthesis) {
            // Load voices
            if (this.speechSynthesis.getVoices().length === 0) {
                this.speechSynthesis.addEventListener('voiceschanged', () => {
                    console.log('Voices loaded:', this.speechSynthesis.getVoices().length);
                });
            }
        }
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
        
        // Speech elements
        this.speechBtn = document.getElementById('speechBtn');
        this.speechToggleBtn = document.getElementById('speechToggleBtn');
        this.speechNotice = document.querySelector('.speech-notice');
        this.speechNoticeText = document.getElementById('speechNoticeText');
        
        // Check and show speech requirements
        this.checkSpeechRequirements();
    }

    checkSpeechRequirements() {
        if (!this.speechNotice || !this.speechNoticeText) return;
        
        const isHTTPS = location.protocol === 'https:';
        const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        const hasSpeechRecognition = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
        
        if (!hasSpeechRecognition) {
            this.speechNoticeText.textContent = 'Speech recognition not supported in this browser';
            this.speechNotice.style.display = 'block';
        } else if (!isHTTPS && !isLocalhost) {
            this.speechNoticeText.innerHTML = 'Speech features require HTTPS. <a href="' + location.href.replace('http:', 'https:') + '" style="color: var(--primary-color);">Switch to HTTPS</a>';
            this.speechNotice.style.display = 'block';
        } else {
            this.speechNoticeText.textContent = 'Click the microphone to speak your message';
            // Show notice initially, hide after user interaction
            this.speechNotice.style.display = 'block';
            setTimeout(() => {
                if (this.speechNotice) {
                    this.speechNotice.style.display = 'none';
                }
            }, 5000);
        }
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

        // Speech event listeners
        if (this.speechBtn) {
            this.speechBtn.addEventListener('click', () => this.toggleSpeechRecognition());
        }
        if (this.speechToggleBtn) {
            this.speechToggleBtn.addEventListener('click', () => this.toggleSpeechSynthesis());
        }
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
        
        // Stop speech when closing chat
        this.stopSpeech();
        if (this.isListening && this.speechRecognition) {
            this.speechRecognition.stop();
        }
    }

    // NEW: hide quick-action buttons container
    hideQuickActions() {
        if (this.quickActionsContainer) {
            this.quickActionsContainer.style.display = 'none';
        }
    }
    handleQuickAction(category) {
        this.hideQuickActions();
        const categoryMessages = {
            customersupport: "Hello",
        };
        const message = categoryMessages[category] || `I'm interested in ${category}.`;
        // this.addMessage(message, 'user');
        this.generateBotResponse(message);
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
    // addOrderCard(order) {
    //     const card = document.createElement('div');
    //     card.className = 'order-card fade-in';
    
    //     const imageUrl = order.product_image || '';  // Fallback if image is missing
    //     const productName = order.product_name || 'Product';
    
    //     card.innerHTML = `
    //         <div class="card mb-2 shadow-sm border">
    //             <div class="row g-0">
    //                 <div class="col-4 product-image">
    //                     <img src="${imageUrl}" alt="${productName}" class="img-fluid rounded-start" onerror="this.style.display='none'" />
    //                 </div>
    //                 <div class="col-8">
    //                     <div class="card-body p-2">
    //                         <h6 class="card-title mb-1 text-truncate">${productName}</h6>
    //                         <p class="card-text mb-1"><strong>Order ID:</strong> ${order.order_id}</p>
    //                         <p class="card-text mb-1"><strong>Status:</strong> ${order.status}</p>
    //                         ${order.order_date ? `<p class="card-text mb-1"><strong>Date:</strong> ${order.order_date}</p>` : ''}
    //                     </div>
    //                 </div>
    //             </div>
    //         </div>
    //     `;
    
    //     this.chatMessages.appendChild(card);
    //     this.scrollToBottom();
    // }
    addOrderCard(order) {
        const card = document.createElement('div');
        card.className = 'order-card fade-in cursor-pointer'; // Add cursor pointer
    
        const imageUrl = order.product_image || '';
        const productName = order.itemname || 'Product';
        const orderId = order.order_id || 'N/A';
        const status = order.status || 'Pending';
        const orderDate = order.order_date || '';
        const invoiceNo = order.invoice_no || '';
        const invoiceUrl = order.invoice_url || '';
    
        card.innerHTML = `
            <div class="card mb-2 shadow-sm border h-100">
                <div class="row g-0">
                    <div class="col-4 product-image">
                        <img src="${imageUrl}" alt="${productName}" class="img-fluid rounded-start" onerror="this.style.display='none'" />
                    </div>
                    <div class="col-8">
                        <div class="card-body p-2">
                            <h6 class="card-title mb-1 text-truncate">${productName}</h6>
                            <p class="card-text mb-1"><strong>Order ID:</strong> ${orderId}</p>
                            ${orderDate ? `<p class="card-text mb-1"><strong>Date:</strong> ${orderDate}</p>` : ''}
                            ${invoiceNo ? `<p class="card-text mb-1"><strong>Invoice No:</strong> ${invoiceNo}</p>` : ''}
                            <p class="card-text mb-1"><strong>Status:</strong> ${status}</p>
                            ${invoiceUrl ? `<a href="${invoiceUrl}" target="_blank" class="btn btn-sm btn-outline-primary mt-2">View Invoice</a>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    
        // Make the card clickable
        card.addEventListener('click', () => {
            const promptText = `This order ${productName} and ${orderId}`;
            console.log('Order card clicked:', promptText);
            this.addMessage(promptText, 'user');
            this.generateBotResponse(promptText);
        });
    
        this.chatMessages.appendChild(card);
        this.scrollToBottom();
    }
    
    
    

    
    // Speech Recognition Methods
    async toggleSpeechRecognition() {
        if (!this.speechRecognition) {
            this.showSpeechStatus('Speech recognition not supported in this browser', true);
            return;
        }

        if (this.isListening) {
            this.speechRecognition.stop();
            return;
        }

        // Check if we're on HTTPS or localhost
        if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
            this.showSpeechStatus('Microphone access requires HTTPS. Please use https:// instead of http://', true);
            return;
        }

        // Check microphone permissions if available
        if ('permissions' in navigator) {
            try {
                const permission = await navigator.permissions.query({ name: 'microphone' });
                if (permission.state === 'denied') {
                    this.showSpeechStatus('Microphone access denied. Please click the microphone icon in your browser\'s address bar to allow access.', true);
                    return;
                }
            } catch (error) {
                console.log('Permission query not supported, continuing with speech recognition');
            }
        }

        // Stop any current speech synthesis
        this.stopSpeech();
        
        try {
            this.speechRecognition.start();
        } catch (error) {
            console.error('Speech recognition start error:', error);
            this.showSpeechStatus('Could not start speech recognition. Please try again.', true);
        }
    }

    updateSpeechButton() {
        if (!this.speechBtn) return;
        
        if (this.isListening) {
            this.speechBtn.classList.add('listening');
            this.speechBtn.title = 'Stop listening';
        } else {
            this.speechBtn.classList.remove('listening');
            this.speechBtn.title = 'Click to speak';
        }
    }

    showSpeechStatus(message, isError = false) {
        // Remove existing status
        this.hideSpeechStatus();
        
        const statusDiv = document.createElement('div');
        statusDiv.className = `speech-status show ${isError ? 'error' : ''}`;
        statusDiv.textContent = message;
        statusDiv.id = 'speechStatus';
        
        this.speechBtn.style.position = 'relative';
        this.speechBtn.appendChild(statusDiv);
        
        if (isError) {
            statusDiv.style.background = 'rgba(220, 53, 69, 0.9)';
            setTimeout(() => this.hideSpeechStatus(), 3000);
        }
    }

    hideSpeechStatus() {
        const existingStatus = document.getElementById('speechStatus');
        if (existingStatus) {
            existingStatus.remove();
        }
    }

    // Speech Synthesis Methods
    toggleSpeechSynthesis() {
        this.speechEnabled = !this.speechEnabled;
        this.updateSpeechToggleButton();
        
        if (!this.speechEnabled) {
            this.stopSpeech();
        }
    }

    updateSpeechToggleButton() {
        if (!this.speechToggleBtn) return;
        
        if (this.speechEnabled) {
            this.speechToggleBtn.classList.remove('muted');
            this.speechToggleBtn.title = 'Bot speech enabled (click to mute)';
            this.speechToggleBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
        } else {
            this.speechToggleBtn.classList.add('muted');
            this.speechToggleBtn.title = 'Bot speech muted (click to enable)';
            this.speechToggleBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
        }
    }

    speak(text) {
        if (!this.speechEnabled || !this.speechSynthesis) return;
        
        // Stop any current speech
        this.stopSpeech();
        
        // Clean the text for better speech synthesis
        const cleanText = this.cleanTextForSpeech(text);
        
        if (cleanText.trim()) {
            this.currentUtterance = new SpeechSynthesisUtterance(cleanText);
            this.currentUtterance.rate = 0.9;
            this.currentUtterance.pitch = 1.0;
            this.currentUtterance.volume = 0.8;
            
            // Try to use a more natural voice if available
            const voices = this.speechSynthesis.getVoices();
            const preferredVoice = voices.find(voice => 
                voice.lang.startsWith('en') && 
                (voice.name.includes('Natural') || voice.name.includes('Enhanced') || voice.name.includes('Premium'))
            ) || voices.find(voice => voice.lang.startsWith('en'));
            
            if (preferredVoice) {
                this.currentUtterance.voice = preferredVoice;
            }
            
            this.currentUtterance.onstart = () => {
                console.log('Speech synthesis started');
            };
            
            this.currentUtterance.onend = () => {
                console.log('Speech synthesis ended');
                this.currentUtterance = null;
            };
            
            this.currentUtterance.onerror = (event) => {
                console.error('Speech synthesis error:', event.error);
                this.currentUtterance = null;
            };
            
            this.speechSynthesis.speak(this.currentUtterance);
        }
    }

    stopSpeech() {
        if (this.speechSynthesis && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
        }
        this.currentUtterance = null;
    }

    cleanTextForSpeech(text) {
        // Remove HTML tags
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = text;
        let cleanText = tempDiv.textContent || tempDiv.innerText || '';
        
        // Remove markdown-style formatting
        cleanText = cleanText
            .replace(/\*\*(.*?)\*\*/g, '$1')  // Bold
            .replace(/\*(.*?)\*/g, '$1')      // Italic
            .replace(/`(.*?)`/g, '$1')        // Code
            .replace(/#{1,6}\s/g, '')         // Headers
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // Links
            .replace(/\n+/g, '. ')            // Line breaks to periods
            .replace(/\s+/g, ' ')             // Multiple spaces to single
            .trim();
        
        return cleanText;
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
                if (answer) {
                    this.addMessage(answer, 'bot');
                    // Speak the bot's response
                    this.speak(answer);
                }
                if (orders && Array.isArray(orders)) orders.forEach(o => this.addOrderCard(o));
                if (products && Array.isArray(products)) products.forEach(p => this.addProductCard(p));
                if (comparison && Array.isArray(comparison)) {
                    comparison.forEach(item => {
                        /* your existing comparison rendering logic */
                    });
                }
                if (end) {
                    this.addMessage(end, 'bot');
                    // Speak the ending message
                    this.speak(end);
                }
            } else if (data.status === "error") {
                const errorMessage = data.data?.answer || "Sorry, an error occurred.";
                this.addMessage(errorMessage, 'bot');
                this.speak(errorMessage);
            } else {
                const fallbackMessage = data.data?.answer || "Sorry, I didn't get that.";
                this.addMessage(fallbackMessage, 'bot');
                this.speak(fallbackMessage);
            }
        })
        .catch(err => {
            console.error("API error:", err);
            this.hideTypingIndicator();
            const errorMessage = `Oops, something went wrong: ${err.message}`;
            this.addMessage(errorMessage, 'bot');
            this.speak(errorMessage);
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
        const welcomeMessage = "Hello! I'm your Lotus Customer Support Assistant. How can I help you today?";
        this.addMessage(welcomeMessage, 'bot');
        // Speak welcome message after a short delay
        setTimeout(() => {
            this.speak(welcomeMessage);
        }, 1000);
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
