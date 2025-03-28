export function truncateText(text, maxChars) {
    return text.length > maxChars ? text.substring(0, maxChars) + '...' : text;
  }