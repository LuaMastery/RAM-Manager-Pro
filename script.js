// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Header scroll effect
const header = document.querySelector('.header');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 100) {
        header.style.background = 'rgba(15, 15, 26, 0.95)';
    } else {
        header.style.background = 'rgba(15, 15, 26, 0.8)';
    }
    
    lastScroll = currentScroll;
});

// Animate elements on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe elements for animation
document.querySelectorAll('.feature-card, .step, .version-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Mockup animation
const mockupProgress = document.querySelector('.mockup-progress');
const mockupPercent = document.querySelector('.mockup-percent');

if (mockupProgress && mockupPercent) {
    let progress = 42;
    setInterval(() => {
        progress = Math.floor(Math.random() * 30) + 40; // Random between 40-70
        mockupProgress.style.width = progress + '%';
        mockupPercent.textContent = progress + '%';
        
        // Change color based on usage
        if (progress < 50) {
            mockupPercent.style.color = '#10b981';
        } else if (progress < 65) {
            mockupPercent.style.color = '#f59e0b';
        } else {
            mockupPercent.style.color = '#ef4444';
        }
    }, 3000);
}

// Add loading animation to download button
document.querySelectorAll('.download-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
        // Only if it's not a real download link yet
        if (this.getAttribute('href') === '#' || this.getAttribute('href').includes('seuusuario')) {
            e.preventDefault();
            
            const originalContent = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Preparando download...';
            this.style.opacity = '0.7';
            
            setTimeout(() => {
                this.innerHTML = originalContent;
                this.style.opacity = '1';
                alert('Download será disponibilizado em breve! O projeto está sendo finalizado.');
            }, 1500);
        }
    });
});

// Stats counter animation
function animateCounter(element, target, duration = 2000) {
    let start = 0;
    const increment = target / (duration / 16);
    
    const timer = setInterval(() => {
        start += increment;
        if (start >= target) {
            element.textContent = target + '+';
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(start) + '+';
        }
    }, 16);
}

// Observe stats for animation
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.classList.contains('animated')) {
            entry.target.classList.add('animated');
            const statNumber = entry.target.querySelector('.stat-number');
            if (statNumber && statNumber.textContent.includes('50')) {
                animateCounter(statNumber, 50);
            }
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('.stat').forEach(stat => {
    statsObserver.observe(stat);
});

// Mobile menu toggle (if needed in future)
const mobileMenuToggle = () => {
    const nav = document.querySelector('.nav-links');
    nav.classList.toggle('mobile-open');
};

// Console easter egg
console.log('%c💾 RAM Manager Pro', 'font-size: 24px; font-weight: bold; color: #6366f1;');
console.log('%cOtimizador de memória profissional para Windows', 'font-size: 14px; color: #a1a1aa;');
console.log('%cVisite: https://github.com/seuusuario/ram-manager-pro', 'font-size: 12px; color: #06b6d4;');
