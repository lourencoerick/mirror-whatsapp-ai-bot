/**
 * Formats a number as Brazilian Real (BRL) currency.
 * Ensures two decimal places.
 *
 * @param {number} value - The numeric value to format.
 * @returns {string} The formatted currency string (e.g., "R$ 1.234,56").
 *                   Returns "R$ --,--" if the input is not a valid number.
 */
export const formatCurrencyBRL = (value: number | null | undefined): string => {
  if (typeof value !== "number" || isNaN(value)) {
    // Handle cases where the input might not be a number as expected
    return "R$ --,--";
  }

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};
