/* Optional reading aid only: exactly one active row, no statistics or data edits. */
(() => {
  const rows = [...document.querySelectorAll('.focus-row')];
  const details = document.getElementById('details');
  const initialText = details.textContent;
  let selected = null, hovered = null, focused = null;

  function refresh() {
    const active = hovered || focused || selected;
    rows.forEach(row => {
      row.classList.toggle('active', row === active);
      row.setAttribute('aria-pressed', String(row === selected));
    });
    details.textContent = active
      ? (active.dataset.detail || active.getAttribute('aria-label'))
      : initialText;
  }

  function choose(row) {
    selected = selected === row ? null : row;
    refresh();
  }

  rows.forEach(row => {
    row.addEventListener('mouseenter', () => { hovered = row; refresh(); });
    row.addEventListener('mouseleave', () => { hovered = null; refresh(); });
    row.addEventListener('focus', () => { focused = row; refresh(); });
    row.addEventListener('blur', () => { focused = null; refresh(); });
    row.addEventListener('click', () => choose(row));
    row.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        choose(row);
      }
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      selected = hovered = focused = null;
      if (rows.includes(document.activeElement)) document.activeElement.blur();
      refresh();
    }
  });
})();
