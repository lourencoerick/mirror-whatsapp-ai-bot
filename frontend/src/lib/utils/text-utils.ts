export function truncateText(text: string, maxChars: number): string {
    return text.length > maxChars ? text.substring(0, maxChars) + '...' : text;
  }