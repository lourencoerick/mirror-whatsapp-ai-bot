// components/landing/WhatsAppButton.tsx
"use client";

import Link from "next/link";
import { FaWhatsapp } from "react-icons/fa";

/**
 * A floating WhatsApp button for the landing page.
 */
export function WhatsAppButton() {
  // Let's get the phone number from environment variables for security and flexibility
  const whatsAppNumber = process.env.NEXT_PUBLIC_SALES_WHATSAPP_NUMBER || "5511941986775";
  const preFilledMessage = "Olá! Vi o site de vocês e gostaria de saber mais sobre a plataforma.";

  if (!whatsAppNumber) {
    // Don't render the button if the number is not configured
    return null;
  }

  const whatsAppLink = `https://wa.me/${whatsAppNumber}?text=${encodeURIComponent(
    preFilledMessage
  )}`;

  return (
    <Link
      href={whatsAppLink}
      target="_blank"
      rel="noopener noreferrer"
      className="fixed bottom-6 right-6 z-50 p-4 bg-green-500 rounded-full shadow-lg hover:bg-green-600 transition-transform duration-300 ease-in-out hover:scale-110"
      aria-label="Fale conosco pelo WhatsApp"
    >
      <FaWhatsapp className="text-white text-3xl" />
    </Link>
  );
}