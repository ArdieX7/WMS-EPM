/* =============================================
   WMS Mobile Navbar JavaScript
   ============================================= */

(function() {
    'use strict';
    
    // Main initialization
    document.addEventListener('DOMContentLoaded', function() {
        // Only initialize on mobile devices
        if (window.innerWidth <= 768) {
            initializeMobileNavbar();
        }
        
        // Re-initialize on window resize
        window.addEventListener('resize', function() {
            if (window.innerWidth <= 768) {
                initializeMobileNavbar();
            } else {
                cleanupMobile();
            }
        });
    });

    function initializeMobileNavbar() {
        initializeUserArea();
        initializeAltroMenu();
        initializeActivePageIndicator();
        // Safe version re-enabled
        optimizeOrdersPageSafe();
    }

    function cleanupMobile() {
        // Clean up mobile event listeners when switching to desktop
        const overlay = document.getElementById('altro-menu-overlay');
        if (overlay) {
            overlay.classList.remove('active');
        }
        const menu = document.getElementById('altro-menu');
        if (menu) {
            menu.classList.remove('active');
        }
    }

    // Initialize mobile user area functionality
    function initializeUserArea() {
        const desktopUserArea = document.getElementById('user-area');
        const desktopLoginArea = document.getElementById('login-area');
        const mobileUserArea = document.getElementById('mobile-user-area');
        const mobileLoginArea = document.getElementById('mobile-login-area');
        
        if (!mobileUserArea || !mobileLoginArea) return;

        // Sync user info from desktop to mobile
        function syncUserAreas() {
            const isLoggedIn = desktopUserArea && desktopUserArea.style.display !== 'none';
            
            if (isLoggedIn) {
                // User is logged in - show mobile user area
                const desktopUserName = document.getElementById('user-name-display');
                const desktopUserRole = document.getElementById('user-role-display');
                const mobileUserName = document.getElementById('mobile-user-name-display');
                const mobileUserRole = document.getElementById('mobile-user-role-display');
                
                if (desktopUserName && mobileUserName) {
                    mobileUserName.textContent = desktopUserName.textContent;
                }
                if (desktopUserRole && mobileUserRole) {
                    mobileUserRole.textContent = desktopUserRole.textContent;
                }
                
                mobileUserArea.style.display = 'flex';
                mobileLoginArea.style.display = 'none';
            } else {
                // User not logged in - show login area
                mobileUserArea.style.display = 'none';
                mobileLoginArea.style.display = 'block';
            }
        }

        // Initial sync
        syncUserAreas();
        
        // Watch for changes in desktop user area visibility
        const observer = new MutationObserver(syncUserAreas);
        if (desktopUserArea) {
            observer.observe(desktopUserArea, { 
                attributes: true, 
                attributeFilter: ['style'] 
            });
        }
        if (desktopLoginArea) {
            observer.observe(desktopLoginArea, { 
                attributes: true, 
                attributeFilter: ['style'] 
            });
        }

        // Mobile logout functionality
        const mobileLogoutBtn = document.getElementById('mobile-logout-button');
        const desktopLogoutBtn = document.getElementById('logout-button');
        
        if (mobileLogoutBtn && desktopLogoutBtn) {
            mobileLogoutBtn.addEventListener('click', function() {
                desktopLogoutBtn.click();
            });
        }
    }

    // Initialize "Altro" menu functionality
    function initializeAltroMenu() {
        const altroBtn = document.getElementById('altro-menu-btn');
        const overlay = document.getElementById('altro-menu-overlay');
        const menu = document.getElementById('altro-menu');
        const closeBtn = document.getElementById('altro-menu-close');
        
        if (!altroBtn || !overlay || !menu || !closeBtn) return;

        // Open menu
        altroBtn.addEventListener('click', function(e) {
            e.preventDefault();
            overlay.classList.add('active');
            setTimeout(() => {
                menu.classList.add('active');
            }, 10); // Small delay for smooth animation
            document.body.style.overflow = 'hidden'; // Prevent background scroll
        });

        // Close menu functions
        function closeMenu() {
            menu.classList.remove('active');
            setTimeout(() => {
                overlay.classList.remove('active');
                document.body.style.overflow = ''; // Restore scroll
            }, 300); // Match CSS transition duration
        }

        // Close on X button
        closeBtn.addEventListener('click', closeMenu);

        // Close on backdrop click
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                closeMenu();
            }
        });

        // Close on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                closeMenu();
            }
        });

        // Close menu when clicking on menu items
        const menuItems = overlay.querySelectorAll('.altro-menu-item');
        menuItems.forEach(item => {
            item.addEventListener('click', function() {
                // Small delay to show click effect, then close
                setTimeout(closeMenu, 150);
            });
        });

        // Handle touch gestures for closing (swipe down)
        let touchStartY = 0;
        let touchEndY = 0;
        
        menu.addEventListener('touchstart', function(e) {
            touchStartY = e.changedTouches[0].screenY;
        });
        
        menu.addEventListener('touchend', function(e) {
            touchEndY = e.changedTouches[0].screenY;
            handleSwipe();
        });
        
        function handleSwipe() {
            if (touchEndY - touchStartY > 100) { // Swipe down threshold
                closeMenu();
            }
        }
    }

    // Initialize active page indicator
    function initializeActivePageIndicator() {
        const currentPath = window.location.pathname;
        const bottomNavItems = document.querySelectorAll('.bottom-navbar .nav-item');
        const altroBtn = document.getElementById('altro-menu-btn');
        const altroMenuItems = document.querySelectorAll('.altro-menu-item');
        
        // Remove all active states first
        bottomNavItems.forEach(item => item.classList.remove('active'));
        if (altroBtn) altroBtn.classList.remove('has-active');
        
        // Check if current page is in bottom nav
        let foundInBottomNav = false;
        bottomNavItems.forEach(item => {
            const href = item.getAttribute('href');
            if (href && currentPath === href) {
                item.classList.add('active');
                foundInBottomNav = true;
            }
        });
        
        // If not found in bottom nav, check altro menu
        if (!foundInBottomNav && altroBtn) {
            altroMenuItems.forEach(item => {
                const href = item.getAttribute('href');
                if (href && (currentPath === href || currentPath.startsWith(href))) {
                    altroBtn.classList.add('has-active');
                    item.classList.add('active');
                }
            });
        }

        // Special handling for home page
        if (currentPath === '/' || currentPath === '') {
            // Don't highlight any nav item for home page
            bottomNavItems.forEach(item => item.classList.remove('active'));
            if (altroBtn) altroBtn.classList.remove('has-active');
        }
    }

    // Handle permission-based visibility
    function handlePermissions() {
        // This function can be extended to hide nav items based on permissions
        // For now, we rely on the existing permission system in modern-auth.js
        const navItems = document.querySelectorAll('[data-permission]');
        
        navItems.forEach(item => {
            const permission = item.getAttribute('data-permission');
            // Permission checking logic would go here
            // This integrates with the existing permission system
        });
    }

    // Utility function to detect if device is mobile
    function isMobileDevice() {
        return window.innerWidth <= 768 || 
               /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    // Optimize orders page for mobile
    function optimizeOrdersPage() {
        // Only run on orders page
        if (!window.location.pathname.includes('/orders')) return;
        
        // Replace text content for mobile optimization - SAFE VERSION
        setTimeout(() => {
            try {
                // Safe text replacements only for specific elements
                
                // 1. Replace in option elements
                const options = document.querySelectorAll('option');
                options.forEach(option => {
                    if (option.textContent && option.textContent.includes('Prodotti in uscita')) {
                        option.textContent = option.textContent.replace('Prodotti in uscita', 'In uscita');
                    }
                });
                
                // 2. Replace in table headers only
                const headers = document.querySelectorAll('th');
                headers.forEach(header => {
                    if (header.textContent && header.textContent.includes('Numero Ordine')) {
                        header.textContent = header.textContent.replace('Numero Ordine', 'Ordine');
                    }
                });
                
                // 3. Make reset sort buttons icon-only
                const resetBtns = document.querySelectorAll('.reset-sort-btn, .reset-sort-inline-btn, #reset-orders-sort-btn');
                resetBtns.forEach(btn => {
                    const text = btn.textContent;
                    if (text && text.includes('Reset')) {
                        const iconMatch = text.match(/[🔄⟲↻🔃]/);
                        if (iconMatch) {
                            btn.innerHTML = iconMatch[0];
                            btn.setAttribute('title', 'Reset Ordinamento');
                        } else {
                            // Fallback to generic reset icon
                            btn.innerHTML = '🔄';
                            btn.setAttribute('title', 'Reset Ordinamento');
                        }
                    }
                });
            } catch (error) {
                console.log('Mobile optimization error (non-critical):', error);
            }
        }, 1000);
    }

    // Safe orders page optimization
    function optimizeOrdersPageSafe() {
        // Only run on orders page
        if (!window.location.pathname.includes('/orders')) return;
        
        setTimeout(() => {
            try {
                // 1. Clean up order details status column - only show icons
                const statusCells = document.querySelectorAll('.mobile-order-details-table tbody td:nth-child(4)');
                statusCells.forEach(cell => {
                    const text = cell.textContent;
                    if (text && text.length > 2) {
                        // Keep only emoji/icons, remove text
                        const iconMatch = text.match(/[✅✓✔️⭐🟢🟡⚠️❌]/); 
                        if (iconMatch) {
                            cell.innerHTML = iconMatch[0];
                        } else if (text.toLowerCase().includes('completo') || text.toLowerCase().includes('complete')) {
                            cell.innerHTML = '✅';
                        } else if (text.toLowerCase().includes('parziale') || text.toLowerCase().includes('partial')) {
                            cell.innerHTML = '🟡';
                        } else if (text.toLowerCase().includes('pending') || text.toLowerCase().includes('in corso')) {
                            cell.innerHTML = '🟡';
                        } else if (text.toLowerCase().includes('errore') || text.toLowerCase().includes('error')) {
                            cell.innerHTML = '❌';
                        }
                    }
                });
                
                // 2. Monitor for dynamically loaded order details
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        if (mutation.type === 'childList') {
                            const addedNodes = Array.from(mutation.addedNodes);
                            addedNodes.forEach(node => {
                                if (node.nodeType === Node.ELEMENT_NODE && 
                                    (node.id === 'order-details-container' || node.querySelector('#order-details-container'))) {
                                    // Re-run status cleanup when order details are loaded
                                    setTimeout(() => {
                                        const newStatusCells = document.querySelectorAll('.mobile-order-details-table tbody td:nth-child(4)');
                                        newStatusCells.forEach(cell => {
                                            const text = cell.textContent;
                                            if (text && text.length > 2) { // Has more than just an icon
                                                const iconMatch = text.match(/[✅✓✔️⭐🟢🟡]/); 
                                                if (iconMatch) {
                                                    cell.innerHTML = iconMatch[0];
                                                } else if (text.toLowerCase().includes('completo')) {
                                                    cell.innerHTML = '✅';
                                                } else if (text.toLowerCase().includes('parziale')) {
                                                    cell.innerHTML = '🟡';
                                                }
                                            }
                                        });
                                    }, 100);
                                }
                            });
                        }
                    });
                });
                
                observer.observe(document.body, { childList: true, subtree: true });
                
            } catch (error) {
                console.log('Safe orders optimization error:', error);
            }
        }, 1000);
    }

    // Public API for integration with existing navbar.js
    window.MobileNavbar = {
        init: initializeMobileNavbar,
        cleanup: cleanupMobile,
        updateActiveIndicator: initializeActivePageIndicator,
        isMobile: isMobileDevice
    };

})();