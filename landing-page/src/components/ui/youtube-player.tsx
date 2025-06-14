import React from 'react';

/**
 * Props for the YouTubePlayer component.
 * @property {string} videoId - The unique ID of the YouTube video.
 * @property {string} title - The accessible title for the video player iframe.
 */
interface YouTubePlayerProps {
  videoId: string;
  title: string;
}

/**
 * A responsive component to embed a YouTube video.
 *
 * This component uses a common CSS trick to maintain the video's 16:9 aspect ratio
 * across different screen sizes.
 *
 * @param {YouTubePlayerProps} props The component props.
 * @returns {React.ReactElement} The rendered YouTube player.
 */
const YouTubePlayer = ({ videoId, title }: YouTubePlayerProps): React.ReactElement => {
  const embedUrl = `https://www.youtube.com/embed/${videoId}`;

  return (
    // This container creates the responsive aspect ratio box.
    <div style={{
      position: 'relative',
      paddingBottom: '56.25%', // 16:9 Aspect Ratio
      height: 0,
      overflow: 'hidden',
      maxWidth: '100%',
    }}>
      <iframe
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
        }}
        src={embedUrl}
        title={title}
        frameBorder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
};

export default YouTubePlayer;