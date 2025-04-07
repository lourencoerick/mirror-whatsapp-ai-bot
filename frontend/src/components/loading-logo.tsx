import React from 'react'

import Image from "next/image";
type Props = {
    size?:number
}

function LoadingLogo({size = 250}: Props) {
  return (
    <div className='h-screen w-full flex justify-center items-center'>
        <Image src="./logo.svg"
            alt="Lambda Labs logo"
            width={size}
            height={size}
            className='animate-pulse duration-800'
        />
    </div>
  )
}

export default LoadingLogo