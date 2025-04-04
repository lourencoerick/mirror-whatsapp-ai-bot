'use client';

import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useSearchParams, usePathname, useRouter } from 'next/navigation';
import { useDebouncedCallback } from 'use-debounce';
import React, { useState, useEffect} from 'react';
import { X } from 'lucide-react';


export default function Search({ placeholder }: { placeholder: string }) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const { refresh, replace } = useRouter();

  const [searchValue, setSearchValue] = useState(searchParams.get('query') || '');

  useEffect(() => {
    setSearchValue(searchParams.get('query') || '');
  }, [searchParams]);


  const handleSearch = useDebouncedCallback((term: string) => {
    const params = new URLSearchParams(searchParams);

    console.log(term);
    if (term) {
      params.set('query', term);
    } else {
      params.delete('query');
    }
    replace(`${pathname}?${params.toString()}`);
    refresh();

  }, 300);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const term = e.target.value;
    setSearchValue(term);
    handleSearch(term);
  };

  const clearSearch = () => {
    setSearchValue('');
    const params = new URLSearchParams(searchParams);
    params.delete('query');
    replace(`${pathname}?${params.toString()}`);
    refresh();
  };

  return (
    <div className="relative w-10/10 self-end px-2">
    
      <label htmlFor="search" className="sr-only">
        Search
      </label>
      <input
        className="peer bg-gray-200 block w-full h-6 rounded-full border border-gray-200 py-[9px] pl-10 text-sm outline-2 placeholder:text-gray-500 focus:ring-2 focus:ring-foreground focus:ring-opacity-50"
        placeholder={placeholder}
        value={searchValue}
        onChange={handleInputChange}
      />
      {searchValue && (
        <button
          type="button"
          onClick={clearSearch}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
        >
          <X size={16} />
        </button>
      )}
      <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-gray-500 peer-focus:text-gray-900" />
    </div>
  );
}
