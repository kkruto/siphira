/* Live Markdown preview under the post body field.
 *
 * Deliberately a small local renderer rather than a CDN library: the admin
 * should keep working offline, and pulling a script from a third party into a
 * logged-in staff page is a needless supply-chain risk. It covers the subset
 * Siphira will actually type; the server (mistune) remains the source of truth
 * for what finally renders on the site.
 */
(function () {
  'use strict';

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function inline(s) {
    return s
      .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, '<img alt="$1" src="$2">')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2">$1</a>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/~~([^~]+)~~/g, '<del>$1</del>');
  }

  function render(src) {
    var lines = escapeHtml(src).split('\n');
    var out = [];
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // Fenced code block
      if (/^```/.test(line)) {
        var buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++;
        out.push('<pre><code>' + buf.join('\n') + '</code></pre>');
        continue;
      }

      // Heading
      var heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        var level = heading[1].length;
        out.push('<h' + level + '>' + inline(heading[2]) + '</h' + level + '>');
        i++;
        continue;
      }

      // Horizontal rule
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push('<hr>'); i++; continue; }

      // Blockquote
      if (/^>\s?/.test(line)) {
        var quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          quote.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        out.push('<blockquote>' + render(quote.join('\n')) + '</blockquote>');
        continue;
      }

      // Lists
      if (/^\s*[-*+]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
        var ordered = /^\s*\d+\.\s+/.test(line);
        var items = [];
        while (i < lines.length &&
               (ordered ? /^\s*\d+\.\s+/.test(lines[i]) : /^\s*[-*+]\s+/.test(lines[i]))) {
          items.push('<li>' + inline(lines[i].replace(/^\s*(?:[-*+]|\d+\.)\s+/, '')) + '</li>');
          i++;
        }
        out.push((ordered ? '<ol>' : '<ul>') + items.join('') + (ordered ? '</ol>' : '</ul>'));
        continue;
      }

      // Blank line
      if (!line.trim()) { i++; continue; }

      // Paragraph — consume until a blank line or a block-level starter.
      var para = [];
      while (i < lines.length && lines[i].trim() &&
             !/^(#{1,6}\s|>\s?|```|\s*[-*+]\s|\s*\d+\.\s)/.test(lines[i])) {
        para.push(lines[i]);
        i++;
      }
      if (para.length) out.push('<p>' + inline(para.join(' ')) + '</p>');
    }

    return out.join('\n');
  }

  function attach(textarea) {
    if (textarea.dataset.mdPreviewAttached) return;
    textarea.dataset.mdPreviewAttached = '1';

    var wrap = document.createElement('div');
    wrap.className = 'md-preview-wrap';

    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'md-preview-toggle';
    toggle.innerHTML = '<span>Live preview</span><span aria-hidden="true">&#9662;</span>';

    var body = document.createElement('div');
    body.className = 'md-preview-body';

    wrap.appendChild(toggle);
    wrap.appendChild(body);
    textarea.parentNode.appendChild(wrap);

    function update() {
      var value = textarea.value.trim();
      body.innerHTML = value
        ? render(textarea.value)
        : '<p class="md-preview-empty">Nothing to preview yet — start typing.</p>';
    }

    var timer = null;
    textarea.addEventListener('input', function () {
      // Debounced: re-rendering on every keystroke makes long posts feel laggy.
      clearTimeout(timer);
      timer = setTimeout(update, 200);
    });

    toggle.addEventListener('click', function () {
      var hidden = body.style.display === 'none';
      body.style.display = hidden ? '' : 'none';
      toggle.lastElementChild.innerHTML = hidden ? '&#9662;' : '&#9656;';
    });

    update();
  }

  document.addEventListener('DOMContentLoaded', function () {
    ['body', 'about_body', 'problem', 'approach', 'progress', 'lessons'].forEach(function (name) {
      var el = document.querySelector('textarea[name="' + name + '"]');
      if (el) attach(el);
    });
  });
})();
