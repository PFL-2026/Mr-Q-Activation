/* PFL × MrQ Activation Strategy 2026 — Navigation logic */
(function () {
  const deck = document.getElementById('deck');
  const slides = Array.from(deck.querySelectorAll('.slide'));
  const navPrev = document.getElementById('navPrev');
  const navNext = document.getElementById('navNext');
  const curSlideEl = document.getElementById('curSlide');
  const progressFill = document.getElementById('progressFill');
  const sectionBtns = Array.from(document.querySelectorAll('.section-btn'));

  // Slide-number → top-nav-section index map
  const SECTION_RANGES = [
    { idx: 0, slides: [1] },
    { idx: 1, slides: [2, 3] },
    { idx: 2, slides: [4, 5, 6, 7, 8] },
    { idx: 3, slides: [9, 10, 11, 12] },
    { idx: 4, slides: [13, 14, 15] },
    { idx: 5, slides: [16] },
    { idx: 6, slides: [17] },
  ];

  const TOTAL_LOGICAL = 17;
  let currentIdx = 0;

  // === Russian events horizontal scroll ===
  const eventsTrack = document.getElementById('eventsTrack');
  let currentEventIdx = 0;
  let totalEvents = 0;
  if (eventsTrack) {
    totalEvents = eventsTrack.querySelectorAll('.event-card').length;
    eventsTrack.addEventListener(
      'scroll',
      () => {
        const w = eventsTrack.clientWidth;
        const newIdx = Math.round(eventsTrack.scrollLeft / w);
        if (newIdx !== currentEventIdx) {
          currentEventIdx = newIdx;
          updateEventUI();
          updateUI();
        }
      },
      { passive: true }
    );
  }

  function updateEventUI() {
    if (!eventsTrack) return;
    const dots = eventsTrack.querySelectorAll('.event-dot');
    dots.forEach((d) => {
      const cardIdx = parseInt(d.dataset.eventIdx, 10);
      d.classList.toggle('active', cardIdx === currentEventIdx);
    });
    const prevs = eventsTrack.querySelectorAll('.ev-prev');
    const nexts = eventsTrack.querySelectorAll('.ev-next');
    prevs.forEach((b) => (b.disabled = currentEventIdx === 0));
    nexts.forEach((b) => (b.disabled = currentEventIdx === totalEvents - 1));
  }

  function goToEvent(idx) {
    if (!eventsTrack) return;
    idx = Math.max(0, Math.min(totalEvents - 1, idx));
    eventsTrack.scrollTo({ left: idx * eventsTrack.clientWidth, behavior: 'smooth' });
  }

  if (eventsTrack) {
    eventsTrack.addEventListener('click', (e) => {
      const dot = e.target.closest('.event-dot');
      if (dot) {
        goToEvent(parseInt(dot.dataset.eventIdx, 10));
        return;
      }
      const prev = e.target.closest('.ev-prev');
      if (prev) {
        goToEvent(currentEventIdx - 1);
        return;
      }
      const next = e.target.closest('.ev-next');
      if (next) {
        goToEvent(currentEventIdx + 1);
        return;
      }
    });
  }

  // === Main deck navigation ===
  function getCurrentSlideIdx() {
    const w = deck.clientWidth;
    return Math.round(deck.scrollLeft / w);
  }

  function getLogicalSlideNumber(slideIdx) {
    const slide = slides[slideIdx];
    if (!slide) return 1;
    return parseInt(slide.dataset.slide || slideIdx + 1, 10);
  }

  function updateUI() {
    const idx = getCurrentSlideIdx();
    currentIdx = idx;
    slides.forEach((s, i) => s.classList.toggle('active', i === idx));
    const logicalNum = getLogicalSlideNumber(idx);
    curSlideEl.textContent = String(logicalNum).padStart(2, '0');
    progressFill.style.width = (logicalNum / TOTAL_LOGICAL) * 100 + '%';

    let activeSection = 0;
    for (const r of SECTION_RANGES) {
      if (r.slides.includes(logicalNum)) {
        activeSection = r.idx;
        break;
      }
    }
    sectionBtns.forEach((b, i) => b.classList.toggle('active', i === activeSection));

    navPrev.disabled = idx === 0 && currentEventIdx === 0;
    navNext.disabled = idx === slides.length - 1;
  }

  function goTo(idx) {
    idx = Math.max(0, Math.min(slides.length - 1, idx));
    deck.scrollTo({ left: idx * deck.clientWidth, behavior: 'smooth' });
  }

  // Instant jump for section-button navigation — no slide-by-slide scroll.
  // Disables snap + smooth-scroll during the jump so the browser commits the new
  // scrollLeft immediately instead of animating through intermediate snap points.
  function goToInstant(idx) {
    idx = Math.max(0, Math.min(slides.length - 1, idx));
    const prevBehavior = deck.style.scrollBehavior;
    const prevSnapType = deck.style.scrollSnapType;
    deck.style.scrollBehavior = 'auto';
    deck.style.scrollSnapType = 'none';
    deck.scrollLeft = idx * deck.clientWidth;
    // Force a reflow so the position commits before snap is re-enabled
    void deck.offsetWidth;
    requestAnimationFrame(() => {
      deck.style.scrollSnapType = prevSnapType;
      deck.style.scrollBehavior = prevBehavior;
      updateUI();
    });
  }

  function goToEventInstant(idx) {
    if (!eventsTrack) return;
    idx = Math.max(0, Math.min(totalEvents - 1, idx));
    const prevBehavior = eventsTrack.style.scrollBehavior;
    const prevSnapType = eventsTrack.style.scrollSnapType;
    eventsTrack.style.scrollBehavior = 'auto';
    eventsTrack.style.scrollSnapType = 'none';
    eventsTrack.scrollLeft = idx * eventsTrack.clientWidth;
    void eventsTrack.offsetWidth;
    requestAnimationFrame(() => {
      eventsTrack.style.scrollSnapType = prevSnapType;
      eventsTrack.style.scrollBehavior = prevBehavior;
      currentEventIdx = idx;
      updateEventUI();
    });
  }

  deck.addEventListener(
    'scroll',
    () => {
      requestAnimationFrame(updateUI);
    },
    { passive: true }
  );

  navPrev.addEventListener('click', () => {
    const slide = slides[currentIdx];
    if (slide && slide.dataset.slideRange && currentEventIdx > 0) {
      goToEvent(currentEventIdx - 1);
    } else {
      goTo(currentIdx - 1);
    }
  });
  navNext.addEventListener('click', () => {
    const slide = slides[currentIdx];
    if (slide && slide.dataset.slideRange && currentEventIdx < totalEvents - 1) {
      goToEvent(currentEventIdx + 1);
    } else {
      goTo(currentIdx + 1);
    }
  });

  sectionBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      // Skip buttons that aren't slide-targets (e.g. Terms Sheet modal trigger)
      if (!btn.dataset.target) return;
      const targetLogical = parseInt(btn.dataset.target, 10);
      let targetIdx = 0;
      for (let i = 0; i < slides.length; i++) {
        const s = slides[i];
        const range = s.dataset.slideRange;
        if (range) {
          const [start, end] = range.split('-').map(Number);
          if (targetLogical >= start && targetLogical <= end) {
            targetIdx = i;
            const evIdx = targetLogical - start;
            goToEventInstant(evIdx);
            goToInstant(targetIdx);
            return;
          }
        }
        if (parseInt(s.dataset.slide, 10) === targetLogical) {
          targetIdx = i;
          break;
        }
      }
      goToInstant(targetIdx);
    });
  });

  document.addEventListener('keydown', (e) => {
    // Defer to any open modal (events / terms / distribution) when one owns focus
    const eventsModal = document.getElementById('eventsModal');
    const termsModal = document.getElementById('termsModal');
    const distModals = document.querySelectorAll('.dist-modal');
    const videoLightbox = document.getElementById('videoLightbox');
    const fgcModal = document.getElementById('fgcModal');
    if (eventsModal && eventsModal.classList.contains('is-open')) return;
    if (termsModal && termsModal.classList.contains('is-open')) return;
    if (videoLightbox && videoLightbox.classList.contains('is-open')) return;
    if (fgcModal && fgcModal.classList.contains('is-open')) return;
    for (const m of distModals) {
      if (m.classList.contains('is-open')) return;
    }
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
      e.preventDefault();
      navNext.click();
    } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
      e.preventDefault();
      navPrev.click();
    } else if (e.key === 'Home') {
      goTo(0);
    } else if (e.key === 'End') {
      goTo(slides.length - 1);
    }
  });

  document.addEventListener(
    'touchmove',
    (e) => {
      if (!e.target.closest('.deck') && !e.target.closest('.events-track')) {
        e.preventDefault();
      }
    },
    { passive: false }
  );

  // === Events Modal (Russian Talent CTA) ===
  // Events are embedded directly in #eventsModalTrack as .em-card elements.
  // This sets up open/close, prev/next, dots, keyboard nav and click-to-close.
  (function setupEventsModal() {
    const modal = document.getElementById('eventsModal');
    if (!modal) return;
    const triggers = document.querySelectorAll('[data-open-events-modal]');
    const closers = modal.querySelectorAll('[data-close-events-modal]');
    const track = modal.querySelector('#eventsModalTrack');
    const dotsEl = modal.querySelector('#eventsModalDots');
    const prevBtn = modal.querySelector('.events-modal-nav.prev');
    const nextBtn = modal.querySelector('.events-modal-nav.next');
    const curEl = modal.querySelector('.events-modal-counter .cur');
    const totalEl = modal.querySelector('.events-modal-counter .total');

    const cards = track.querySelectorAll('.em-card');
    const total = cards.length;
    if (!total) return;
    if (totalEl) totalEl.textContent = total;

    // Build dots
    for (let i = 0; i < total; i++) {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'em-dot';
      dot.setAttribute('aria-label', 'Event ' + (i + 1));
      dot.addEventListener('click', () => goTo(i));
      dotsEl.appendChild(dot);
    }
    const dots = dotsEl.querySelectorAll('.em-dot');

    let activeIdx = 0;
    function goTo(i) {
      activeIdx = Math.max(0, Math.min(total - 1, i));
      cards.forEach((c, ci) => c.classList.toggle('is-active', ci === activeIdx));
      dots.forEach((d, di) => d.classList.toggle('is-active', di === activeIdx));
      if (curEl) curEl.textContent = activeIdx + 1;
      if (prevBtn) prevBtn.disabled = activeIdx === 0;
      if (nextBtn) nextBtn.disabled = activeIdx === total - 1;
    }

    function openModal(startIdx) {
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('events-modal-open');
      goTo(typeof startIdx === 'number' ? startIdx : 0);
    }
    function closeModal() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('events-modal-open');
    }

    triggers.forEach(t => t.addEventListener('click', () => openModal(0)));
    closers.forEach(c => c.addEventListener('click', closeModal));
    if (prevBtn) prevBtn.addEventListener('click', () => goTo(activeIdx - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goTo(activeIdx + 1));

    document.addEventListener('keydown', (e) => {
      if (!modal.classList.contains('is-open')) return;
      if (e.key === 'Escape') { closeModal(); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); goTo(activeIdx + 1); }
      else if (e.key === 'ArrowLeft')  { e.preventDefault(); goTo(activeIdx - 1); }
    });
  })();

  // === Terms Sheet Modal ===
  // Opens the terms sheet in an overlay; "Download PDF" triggers the browser's
  // print dialog with a print-specific stylesheet that re-renders the content
  // for paper. User picks "Save as PDF" in the print dialog.
  (function setupTermsModal() {
    const modal = document.getElementById('termsModal');
    if (!modal) return;
    const triggers = document.querySelectorAll('[data-open-terms-modal]');
    const closers = modal.querySelectorAll('[data-close-terms-modal]');
    const printBtn = modal.querySelector('[data-print-terms]');

    function openModal() {
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('terms-modal-open');
    }
    function closeModal() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('terms-modal-open');
    }
    function printTerms() {
      // The print stylesheet shows only #termsModal contents formatted for paper.
      // Most browsers default to "Save as PDF" in the print dialog destination.
      window.print();
    }

    triggers.forEach(t => t.addEventListener('click', openModal));
    closers.forEach(c => c.addEventListener('click', closeModal));
    if (printBtn) printBtn.addEventListener('click', printTerms);

    document.addEventListener('keydown', (e) => {
      if (!modal.classList.contains('is-open')) return;
      if (e.key === 'Escape') { closeModal(); }
    });
  })();

  // === Distribution & Reach Modals ===
  // Broadcast (slide 4) and Social (slide 8) — same shell pattern as terms.
  // Each trigger has data-open-dist-modal="<modalId>".
  (function setupDistModals() {
    const modals = document.querySelectorAll('.dist-modal');
    if (!modals.length) return;
    const triggers = document.querySelectorAll('[data-open-dist-modal]');

    function openDistModal(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('terms-modal-open');
    }
    function closeAllDist() {
      modals.forEach(m => {
        m.classList.remove('is-open');
        m.setAttribute('aria-hidden', 'true');
      });
      document.body.classList.remove('terms-modal-open');
    }

    triggers.forEach(t => {
      t.addEventListener('click', () => openDistModal(t.dataset.openDistModal));
    });
    modals.forEach(modal => {
      modal.querySelectorAll('[data-close-dist-modal]').forEach(c => {
        c.addEventListener('click', closeAllDist);
      });
      modal.querySelectorAll('[data-print-dist]').forEach(p => {
        p.addEventListener('click', () => window.print());
      });
    });

    document.addEventListener('keydown', (e) => {
      const anyOpen = Array.from(modals).some(m => m.classList.contains('is-open'));
      if (!anyOpen) return;
      if (e.key === 'Escape') { closeAllDist(); }
    });
  })();

  // FGC detail modal — content showcase for slide 11
  (function setupFgcModal() {
    const modal = document.getElementById('fgcModal');
    if (!modal) return;
    const content = document.getElementById('fgcModalContent');
    const triggers = document.querySelectorAll('.fgc-explore');

    const DATA = {
      'event-night': {
        eyebrow: 'Fighter Generated Content',
        title: 'Event Night',
        desc: 'MrQ at the centre of fight night — money-can\'t-buy fan experiences and guaranteed PFL star power that put the brand face-to-face with fans at every event.',
        videos: [
          {
            src: 'assets/video/event/meet_greet', label: 'Fighter Meet & Greet',
            vdesc: 'Money-can\'t-buy access for fans and competition winners — signings, photos and face time with PFL stars, delivered as MrQ-branded experiences.'
          },
          {
            src: 'assets/video/event/athlete_attendance', label: 'Athlete Attendance',
            vdesc: 'Athletes and celebrities on-site and in the crowd — guaranteed star power that pulls fans, cameras and content on fight night.'
          }
        ]
      },
      'fight-highlights': {
        eyebrow: 'Fighter Generated Content',
        title: 'Automated Fight Highlights',
        clickToPlay: true,
        desc: 'Automated, broadcast-quality highlight packages cut within minutes of every PFL fight — delivered to MrQ to repurpose across owned channels, driving engagement and excitement around every event. All powered by WSC Sports.',
        videos: [
          {
            src: 'assets/video/highlights/full_fight_highlights', label: 'Full Fight Highlights',
            vdesc: 'Every key exchange from first bell to final result, cut into a single shareable package.'
          },
          {
            src: 'assets/video/highlights/archive_footage', label: 'Archive Footage',
            vdesc: 'Classic moments from the PFL vault, ready to repackage around upcoming matchups and storylines.'
          },
          {
            src: 'assets/video/highlights/knockouts', label: 'Knockouts',
            vdesc: 'The biggest finishes, clipped and delivered minutes after they land — built for instant social impact.'
          },
          {
            src: 'assets/video/highlights/strike_combinations', label: 'Strike Combinations',
            vdesc: 'Bite-size technical breakdowns of the cleanest combinations, made for fight-fan feeds.'
          }
        ]
      },
      'face-offs': {
        eyebrow: 'Fighter Generated Content',
        title: 'Fighter Face-Offs',
        desc: 'The tension of the staredown, frame by frame. High-impact face-off content built for virality and primed to drive engagement around every marquee matchup.',
        videos: [
          { src: 'assets/video/fgc/faceoff_dubai', label: 'PFL Dubai' },
          { src: 'assets/video/fgc/faceoff_madrid', label: 'PFL Madrid' },
          { src: 'assets/video/fgc/faceoff_paris', label: 'PFL Paris' },
          { src: 'assets/video/fgc/faceoff_nashville', label: 'PFL Nashville' }
        ]
      },
      'content-series': {
        eyebrow: 'Fighter Generated Content',
        title: 'Original Content Series',
        desc: 'Episodic, story-led content following fighters through camp, fight week and beyond — a recurring series that keeps MrQ front and centre between events.',
        series: [
          {
            label: 'Between Rounds',
            embed: 'https://www.youtube.com/embed/Z56rQeSApBY',
            archive: 'https://www.youtube.com/playlist?list=PL2PVbMNCCWz6W0zBXMa_6jsfIXJFt6iXg',
            desc: 'Long-form sit-downs with the biggest personalities in the PFL, hosted by Dan Hardy — fighters, coaches, execs, on life, legacy and the stories behind the fights.'
          },
          {
            label: 'PFL Origins',
            embed: 'https://www.youtube.com/embed/Yodxdi5O6Ao',
            archive: 'https://www.youtube.com/playlist?list=PL2PVbMNCCWz47LXCXGImUhA4-Y6RBV3Gy',
            desc: 'Documentary-style storytelling tracing each fighter\'s road to the PFL — where they came from, what they overcame and what drives them.'
          }
        ]
      }
    };

    function placeholders(n) {
      let html = '<div class="fgc-modal-videos">';
      for (let i = 0; i < n; i++) {
        html += '<div class="fgc-video-placeholder">'
          + '<svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'
          + '<span>Video / imagery coming soon</span></div>';
      }
      html += '</div>';
      return html;
    }

    function videoGrid(videos, clickToPlay) {
      let html = '<div class="fgc-modal-videos">';
      videos.forEach(v => {
        const attrs = clickToPlay
          ? 'preload="metadata"'
          : 'autoplay muted loop playsinline preload="auto"';
        const labelCls = clickToPlay ? 'fgc-video-label fgc-video-label--ctp' : 'fgc-video-label';
        html += '<div class="fgc-series-box">'
          + '<div class="fgc-video-box' + (clickToPlay ? ' fgc-video-box--ctp' : '') + '">'
          + '<video ' + attrs + ' playsinline>'
          + '<source src="' + v.src + '.mp4" type="video/mp4">'
          + '</video>'
          + (clickToPlay
              ? '<button type="button" class="fgc-play-btn" aria-label="Play ' + v.label + '">'
                + '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'
                + '</button>'
              : '')
          + '<span class="' + labelCls + '">' + v.label + '</span>'
          + '</div>'
          + (v.vdesc ? '<p class="fgc-series-desc">' + v.vdesc + '</p>' : '')
          + '</div>';
      });
      html += '</div>';
      return html;
    }

    function seriesGrid(series) {
      let html = '<div class="fgc-modal-videos">';
      series.forEach(s => {
        html += '<div class="fgc-series-box">'
          + '<div class="fgc-embed">'
          + '<iframe src="' + s.embed + '" title="' + s.label + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>'
          + '<span class="fgc-video-label fgc-embed-label">' + s.label + '</span>'
          + '</div>'
          + '<p class="fgc-series-desc">' + s.desc + '</p>'
          + '<a class="fgc-archive-btn" href="' + s.archive + '" target="_blank" rel="noopener">' + s.label + ' — Full Archive&nbsp;→</a>'
          + '</div>';
      });
      html += '</div>';
      return html;
    }

    function open(key) {
      const d = DATA[key];
      if (!d) return;
      content.innerHTML =
        (d.cover ? '<img class="fgc-cover" src="' + d.cover + '" alt="">' : '') +
        '<div class="fgc-modal-eyebrow">' + d.eyebrow + '</div>' +
        '<h2 class="fgc-modal-title">' + d.title + '</h2>' +
        '<p class="fgc-modal-desc">' + d.desc + '</p>' +
        (d.series ? seriesGrid(d.series) : d.videos ? videoGrid(d.videos, d.clickToPlay) : placeholders(4));
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      // Kick autoplay in browsers that ignore the attribute on injected nodes
      content.querySelectorAll('video[autoplay]').forEach(v => { v.play().catch(() => {}); });
      content.querySelectorAll('.fgc-play-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const box = btn.closest('.fgc-video-box');
          const video = box.querySelector('video');
          box.classList.add('is-playing');
          video.setAttribute('controls', '');
          video.play().catch(() => {});
        });
      });
    }
    function close() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      content.innerHTML = '';
    }

    triggers.forEach(t => {
      t.addEventListener('click', (e) => {
        e.stopPropagation();
        open(t.getAttribute('data-fgc'));
      });
    });
    modal.querySelectorAll('[data-close-fgc]').forEach(c => c.addEventListener('click', close));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('is-open')) close();
    });
  })();

  // Video lightbox — embeds the demo video inside the deck
  (function setupVideoLightbox() {
    const lightbox = document.getElementById('videoLightbox');
    if (!lightbox) return;
    const frame = document.getElementById('videoLightboxFrame');
    const triggers = document.querySelectorAll('.video-embed-trigger');

    function openVideo(src) {
      frame.innerHTML = '<iframe src="' + src + '" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>';
      lightbox.classList.add('is-open');
      lightbox.setAttribute('aria-hidden', 'false');
    }
    function closeVideo() {
      lightbox.classList.remove('is-open');
      lightbox.setAttribute('aria-hidden', 'true');
      frame.innerHTML = ''; // stop playback
    }

    triggers.forEach(t => {
      t.addEventListener('click', () => openVideo(t.getAttribute('data-video-src')));
    });
    lightbox.querySelectorAll('[data-close-video]').forEach(c => {
      c.addEventListener('click', closeVideo);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && lightbox.classList.contains('is-open')) closeVideo();
    });
  })();

  // Slide 12 — Watch & Bet player: click the trigger to open & play the stream
  (function setupWatchBetPlayer() {
    const frame = document.querySelector('.wb-stage .wb-frame');
    if (!frame) return;
    const trigger = frame.querySelector('.wb-play-trigger');
    const player = frame.querySelector('.wb-player');
    const video = frame.querySelector('.wb-video');
    const closeBtn = frame.querySelector('.wb-player-close');

    function openPlayer() {
      frame.classList.add('is-playing');
      if (player) player.setAttribute('aria-hidden', 'false');
      if (video) { try { video.currentTime = 0; video.play(); } catch (e) {} }
    }
    function closePlayer() {
      frame.classList.remove('is-playing');
      if (player) player.setAttribute('aria-hidden', 'true');
      if (video) { try { video.pause(); } catch (e) {} }
    }

    if (trigger) trigger.addEventListener('click', openPlayer);
    if (closeBtn) closeBtn.addEventListener('click', (e) => { e.stopPropagation(); closePlayer(); });
  })();

  // Init
  updateUI();
  if (eventsTrack) updateEventUI();
})();

/* === See Brand in Action modal (slide 4) === */
(function () {
  const modal    = document.getElementById('sbiaModal');
  const openBtn  = document.getElementById('sbiaOpen');
  const closeBtn = document.getElementById('sbiaClose');
  const backdrop = document.getElementById('sbiaBackdrop');
  const videos   = modal ? Array.from(modal.querySelectorAll('video')) : [];

  if (!modal || !openBtn) return;

  function openModal() {
    modal.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    closeBtn.focus();
  }

  function closeModal() {
    modal.classList.remove('is-open');
    document.body.style.overflow = '';
    videos.forEach(v => { v.pause(); v.currentTime = 0; });
    openBtn.focus();
  }

  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) {
      e.stopImmediatePropagation();
      closeModal();
    }
  }, true); // capture phase — fires before deck arrow-key handler
})();
