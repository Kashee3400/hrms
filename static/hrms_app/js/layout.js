/**
 * layout.js
 * Core layout functionality: sidebar toggle, right sidebar, and responsive behavior
 */

document.addEventListener('DOMContentLoaded', function() {
  // ============================================
  // SIDEBAR TOGGLE
  // ============================================

  const toggleButton = document.getElementById('toggle-sidebar');
  const sidebar = document.getElementById('sidebar');
  const appContainer = document.querySelector('.app-container');

  if (toggleButton && sidebar) {
    toggleButton.addEventListener('click', function(e) {
      e.stopPropagation();
      sidebar.classList.toggle('active');
      appContainer.classList.toggle('sidebar-open');
    });
  }

  // Close sidebar when clicking on a link
  if (sidebar) {
    const sidebarLinks = sidebar.querySelectorAll('a');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 767) {
          sidebar.classList.remove('active');
          appContainer.classList.remove('sidebar-open');
        }
      });
    });
  }

  // Close sidebar when clicking outside
  if (sidebar && appContainer) {
    document.addEventListener('click', function(e) {
      if (window.innerWidth <= 767) {
        const isClickInsideSidebar = sidebar.contains(e.target);
        const isToggleButton = toggleButton && toggleButton.contains(e.target);

        if (!isClickInsideSidebar && !isToggleButton && sidebar.classList.contains('active')) {
          sidebar.classList.remove('active');
          appContainer.classList.remove('sidebar-open');
        }
      }
    });
  }

  // ============================================
  // RIGHT SIDEBAR (NOTIFICATIONS/SETTINGS)
  // ============================================

  const rightSidebar = document.getElementById('right-sidebar');
  const settingsToggleButton = document.getElementById('settings-toggle');
  const rightSidebarClose = rightSidebar ? rightSidebar.querySelector('.settings-close') : null;

  if (settingsToggleButton && rightSidebar) {
    settingsToggleButton.addEventListener('click', function(e) {
      e.stopPropagation();
      rightSidebar.classList.toggle('active');
    });
  }

  if (rightSidebarClose && rightSidebar) {
    rightSidebarClose.addEventListener('click', function(e) {
      e.stopPropagation();
      rightSidebar.classList.remove('active');
    });
  }

  // Close right sidebar when clicking outside
  if (rightSidebar) {
    document.addEventListener('click', function(e) {
      const isClickInsideRightSidebar = rightSidebar.contains(e.target);
      const isSettingsToggle = settingsToggleButton && settingsToggleButton.contains(e.target);

      if (!isClickInsideRightSidebar && !isSettingsToggle && rightSidebar.classList.contains('active')) {
        rightSidebar.classList.remove('active');
      }
    });
  }

  // ============================================
  // ALERT DISMISSAL
  // ============================================

  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    const closeButton = alert.querySelector('.btn-close');
    if (closeButton) {
      closeButton.addEventListener('click', function() {
        alert.style.animation = 'slideUp 0.3s ease-out forwards';
        setTimeout(() => {
          alert.remove();
        }, 300);
      });
    }
  });

  // Auto-dismiss success alerts after 5 seconds
  const successAlerts = document.querySelectorAll('.alert-success');
  successAlerts.forEach(alert => {
    setTimeout(() => {
      if (alert.parentElement) { // Check if still in DOM
        alert.style.animation = 'slideUp 0.3s ease-out forwards';
        setTimeout(() => {
          alert.remove();
        }, 300);
      }
    }, 5000);
  });

  // ============================================
  // RESPONSIVE BEHAVIOR
  // ============================================

  function handleResize() {
    const width = window.innerWidth;

    // Close sidebar on mobile when resizing to desktop
    if (width > 767 && sidebar) {
      sidebar.classList.remove('active');
      appContainer.classList.remove('sidebar-open');
    }

    // Close right sidebar on mobile when resizing to desktop
    if (width > 767 && rightSidebar) {
      rightSidebar.classList.remove('active');
    }
  }

  window.addEventListener('resize', handleResize);

  // ============================================
  // SCROLL BEHAVIOR
  // ============================================

  const contentWrapper = document.querySelector('.content-wrapper');

  if (contentWrapper) {
    // Add scroll shadow to navbar
    contentWrapper.addEventListener('scroll', function() {
      const navbar = document.querySelector('.navbar');
      if (navbar) {
        if (contentWrapper.scrollTop > 0) {
          navbar.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
        } else {
          navbar.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.04)';
        }
      }
    });
  }

  // ============================================
  // KEYBOARD SHORTCUTS
  // ============================================

  document.addEventListener('keydown', function(e) {
    // Escape key to close sidebars
    if (e.key === 'Escape') {
      if (sidebar && sidebar.classList.contains('active')) {
        sidebar.classList.remove('active');
        appContainer.classList.remove('sidebar-open');
      }
      if (rightSidebar && rightSidebar.classList.contains('active')) {
        rightSidebar.classList.remove('active');
      }
    }
  });

  // ============================================
  // MOBILE NAVBAR ADJUSTMENT
  // ============================================

  function adjustForMobileNotch() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const isNotchPhone = window.innerHeight > 800 && window.innerWidth < 400;

    if (isIOS || isNotchPhone) {
      // Add padding to account for notch
      const navbar = document.querySelector('.navbar');
      if (navbar) {
        navbar.style.paddingTop = 'max(var(--navbar-height), env(safe-area-inset-top))';
      }
    }
  }

  adjustForMobileNotch();
  window.addEventListener('orientationchange', adjustForMobileNotch);

  // ============================================
  // FORM VALIDATION STYLING
  // ============================================

  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    form.addEventListener('submit', function(e) {
      const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
      let isValid = true;

      inputs.forEach(input => {
        if (!input.value.trim()) {
          input.style.borderColor = '#ef4444';
          input.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
          isValid = false;
        } else {
          input.style.borderColor = '';
          input.style.boxShadow = '';
        }

        input.addEventListener('input', function() {
          if (this.value.trim()) {
            this.style.borderColor = '';
            this.style.boxShadow = '';
          }
        });
      });

      if (!isValid) {
        e.preventDefault();
      }
    });
  });

  // ============================================
  // ACCESSIBILITY ENHANCEMENTS
  // ============================================

  // Ensure all interactive elements have proper focus states
  const interactiveElements = document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]');
  interactiveElements.forEach(element => {
    element.addEventListener('focus', function() {
      this.style.outline = '2px solid var(--primary-color)';
      this.style.outlineOffset = '2px';
    });

    element.addEventListener('blur', function() {
      this.style.outline = '';
    });
  });

  // ============================================
  // INITIALIZE TOOLTIPS (if using Bootstrap)
  // ============================================

  if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  // ============================================
  // LOCAL STORAGE FOR SIDEBAR STATE
  // ============================================

  // Remember sidebar state on desktop
  const sidebarState = localStorage.getItem('sidebar-state');
  if (sidebarState === 'closed' && window.innerWidth > 767 && sidebar) {
    sidebar.classList.add('collapsed');
  }

  if (toggleButton) {
    toggleButton.addEventListener('click', function() {
      if (window.innerWidth > 767) {
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebar-state', isCollapsed ? 'open' : 'closed');
      }
    });
  }
});

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Type of alert (success, info, warning, danger)
 * @param {number} duration - Duration in milliseconds (default: 5000)
 */
function showNotification(message, type = 'info', duration = 5000) {
  const messagesContainer = document.querySelector('.messages-container') || createMessagesContainer();
  const alertElement = document.createElement('div');
  
  alertElement.className = `alert alert-${type} alert-dismissible fade show`;
  alertElement.setAttribute('role', 'alert');
  
  alertElement.innerHTML = `
    <div class="alert-content">
      <span class="alert-message">${message}</span>
    </div>
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;

  messagesContainer.appendChild(alertElement);

  // Auto-dismiss
  setTimeout(() => {
    alertElement.style.animation = 'slideUp 0.3s ease-out forwards';
    setTimeout(() => alertElement.remove(), 300);
  }, duration);

  // Close button handler
  const closeButton = alertElement.querySelector('.btn-close');
  closeButton.addEventListener('click', function() {
    alertElement.style.animation = 'slideUp 0.3s ease-out forwards';
    setTimeout(() => alertElement.remove(), 300);
  });
}

/**
 * Create messages container if it doesn't exist
 */
function createMessagesContainer() {
  const contentInner = document.querySelector('.content-inner');
  const container = document.createElement('div');
  container.className = 'messages-container';
  
  if (contentInner) {
    contentInner.insertBefore(container, contentInner.firstChild);
  } else {
    document.body.insertBefore(container, document.body.firstChild);
  }

  return container;
}

/**
 * Add CSS animation for slide up
 */
const style = document.createElement('style');
style.textContent = `
  @keyframes slideUp {
    to {
      opacity: 0;
      transform: translateY(-20px);
    }
  }
`;
document.head.appendChild(style);