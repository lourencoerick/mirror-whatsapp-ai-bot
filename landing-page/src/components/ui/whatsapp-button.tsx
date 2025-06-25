// components/landing/WhatsAppButton.tsx
"use client";

import { trackEvent } from "@/lib/analytics"; // 1. Import our analytics helper
import React from "react";
import { FaWhatsapp } from "react-icons/fa";

/**
 * A floating WhatsApp button for the landing page that tracks clicks.
 */
export function WhatsAppButton() {
  const whatsAppNumber = process.env.NEXT_PUBLIC_SALES_WHATSAPP_NUMBER || "5511941986775";
  const preFilledMessage = "Olá! Vi o site de vocês e gostaria de saber mais sobre a plataforma.";

  if (!whatsAppNumber) {
    return null;
  }

  const whatsAppLink = `https://wa.me/${whatsAppNumber}?text=${encodeURIComponent(
    preFilledMessage
  )}`;

  /**
   * Handles the click event, tracks it, and then navigates the user to WhatsApp.
   * @param {React.MouseEvent<HTMLAnchorElement>} e - The mouse event.
   */
  const handleWhatsAppClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Prevent the link from navigating immediately, so we can track first.
    e.preventDefault();

    const openWhatsAppLink = () => {
      window.open(whatsAppLink, '_blank', 'noopener,noreferrer');
    };

    // We reuse the 'generate_lead' event name for consistency.
    // The 'location' parameter is the key differentiator.
    trackEvent(
      'generate_lead',
      {
        lead_type: 'whatsapp',
        location: 'floating_action_button', // Differentiates this from the in-page button
      },
      openWhatsAppLink
    );
  };

  return (
    // We change from Link to a standard <a> tag and add our onClick handler.
    <a
      href={whatsAppLink}
      onClick={handleWhatsAppClick}
      target="_blank"
      rel="noopener noreferrer"
      className="fixed bottom-6 right-6 z-50 p-4 bg-green-500 rounded-full shadow-lg hover:bg-green-600 transition-transform duration-300 ease-in-out hover:scale-110"
      aria-label="Fale conosco pelo WhatsApp"
    >
      <FaWhatsapp className="text-white text-3xl" />
    </a>
  );
}