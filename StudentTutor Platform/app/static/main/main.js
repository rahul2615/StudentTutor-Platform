/* ==========================================================================
   EDUCONNECT — INTERACTIVE CLIENT LOGIC & ANIMATIONS
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {

  // ── Mobile Nav Toggle (with aria & keyboard support) ────
  const navToggle = document.getElementById('navToggle');
  const navMenu = document.getElementById('navMenu');

  if (navToggle && navMenu) {
    function toggleNav() {
      const isActive = navMenu.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', isActive ? 'true' : 'false');
      const icon = navToggle.querySelector('i');
      if (icon) {
        icon.classList.toggle('fa-bars', !isActive);
        icon.classList.toggle('fa-times', isActive);
      }
    }

    navToggle.addEventListener('click', toggleNav);

    navToggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleNav();
      }
    });

    document.addEventListener('click', (e) => {
      if (!navToggle.contains(e.target) && !navMenu.contains(e.target)) {
        navMenu.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
        const icon = navToggle.querySelector('i');
        if (icon) {
          icon.classList.remove('fa-times');
          icon.classList.add('fa-bars');
        }
      }
    });
  }

  // ── Animated Stat Number Counters ────────────────────────
  const statCounters = document.querySelectorAll('.stat-counter');

  function animateCounter(el) {
    const target = parseInt(el.getAttribute('data-target') || el.innerText, 10);
    if (isNaN(target) || target === 0) return;

    let start = 0;
    const duration = 1200;
    const startTime = performance.now();

    function updateCount(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic formula
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      const currentVal = Math.floor(easeProgress * target);
      el.innerText = currentVal;

      if (progress < 1) {
        requestAnimationFrame(updateCount);
      } else {
        el.innerText = target;
      }
    }

    requestAnimationFrame(updateCount);
  }

  if (statCounters.length > 0) {
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            obs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.2 });

      statCounters.forEach(counter => observer.observe(counter));
    } else {
      statCounters.forEach(counter => animateCounter(counter));
    }
  }

  // ── Staggered Entrance Animations for Lists/Grids ───────
  const staggerGrids = document.querySelectorAll('.animate-stagger');
  staggerGrids.forEach(grid => {
    const children = grid.children;
    Array.from(children).forEach((child, idx) => {
      child.style.animationDelay = `${idx * 60}ms`;
      child.classList.add('animate-fade-in-up');
    });
  });

  // ── Live Course Search Filter ────────────────────────────
  const courseSearchInput = document.getElementById('courseSearchInput');
  if (courseSearchInput) {
    courseSearchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase().trim();
      const courseCards = document.querySelectorAll('.course-card-item');

      courseCards.forEach((card) => {
        const title = card.getAttribute('data-title') || '';
        const desc = card.getAttribute('data-desc') || '';
        const tutor = card.getAttribute('data-tutor') || '';

        if (title.includes(term) || desc.includes(term) || tutor.includes(term)) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  }

  // ── Auto-dismiss Flash Alerts ────────────────────────────
  const flashAlerts = document.querySelectorAll('.flash-container .alert');
  flashAlerts.forEach((alert) => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    }, 6000);
  });

});
