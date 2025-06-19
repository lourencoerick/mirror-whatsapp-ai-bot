// components/icons/google-icon.tsx
import { SVGProps } from "react";

/**
 * Renders the Google 'G' logo icon.
 * @param {SVGProps<SVGSVGElement>} props - Standard SVG props.
 */
export function GoogleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 48 48"
      width="1em" // Makes the icon scale with the parent's font size
      height="1em"
      {...props}
    >
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039L38.804 12.81C34.978 9.283 29.865 7 24 7 12.955 7 4 15.955 4 27s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 13 24 13c3.059 0 5.842 1.154 7.961 3.039l6.545-6.218C34.978 9.283 29.865 7 24 7 16.318 7 9.656 10.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 47c5.865 0 10.978-2.283 14.804-5.81l-6.545-6.218C29.842 36.846 27.059 38 24 38c-5.223 0-9.651-3.358-11.297-7.962l-6.571 4.819C9.656 41.663 16.318 47 24 47z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l6.571 4.819c3.93-3.597 6.216-8.832 6.216-14.389 0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}
