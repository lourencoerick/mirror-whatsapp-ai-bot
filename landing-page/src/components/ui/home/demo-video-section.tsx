"use client";

import YouTubePlayer from '@/components/ui/youtube-player';
import React from 'react';
import { Element } from 'react-scroll';

/**
 * The section of the homepage that displays the product demo video.
 * It's wrapped in a react-scroll Element for smooth scrolling navigation.
 * @returns {React.ReactElement} The rendered demo video section.
 */
const DemoVideoSection = (): React.ReactElement => {
  
  const demoVideoId = 'erordBBnEu0';

  return (
    // We use the <Element> component from react-scroll as the section's root.
    // The `name` prop is what the <ScrollLink to="..."> will target.
    <Element name="demo" className="py-6 md:py-12 bg-secondary text-secondary-foreground">
      <div className="container mx-auto px-6">
        <div className="text-center">
          <h2 className="text-3xl md:text-4xl  mb-4">
            Veja em Ação
          </h2>
          <p className="text-lg mb-10">
            Assista a este vídeo de 4 minutos e veja como é fácil <span className="font-bold">automatizar suas vendas.</span>
          </p>
        </div>
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-2xl overflow-hidden">
          <YouTubePlayer
            videoId={demoVideoId}
            title="Demonstração do Produto"
          />
        </div>
      </div>
    </Element>
  );
};

export default DemoVideoSection;