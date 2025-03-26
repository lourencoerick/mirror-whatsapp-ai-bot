/**
 * Formats a Brazilian phone number string into the format: +55 11 94198-6777
 *
 * @param phoneNumber - Raw phone number string (e.g., '5511941986777')
 * @returns Formatted phone number or original string if invalid
 */
export function formatPhoneNumber(phoneNumber: string): string {
    const cleaned = phoneNumber.replace(/\D/g, ''); // remove non-numeric characters
  
    const match = cleaned.match(/^(\d{2})(\d{2})(\d{5})(\d{4})$/);
    if (!match) return phoneNumber; // fallback to original if format doesn't match
  
    const [, country, area, prefix, line] = match;
    return `+${country} ${area} ${prefix}-${line}`;
  }
  