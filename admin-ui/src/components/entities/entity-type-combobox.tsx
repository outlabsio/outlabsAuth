import { useState, useEffect } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useEntityTypes } from '@/hooks/use-entity-types';
import { EntityClass, getEntityTypeLabel } from '@/types/entity';
import { Badge } from '@/components/ui/badge';

interface EntityTypesResponse {
  suggestions: Array<{
    entity_type: string;
    count: number;
    last_used?: string;
    is_predefined?: boolean;
  }>;
  total: number;
}

interface EntityTypeComboboxProps {
  value: string;
  onChange: (value: string) => void;
  entityClass?: EntityClass;
  platformId?: string;
  disabled?: boolean;
  placeholder?: string;
}

export function EntityTypeCombobox({
  value,
  onChange,
  entityClass,
  platformId,
  disabled = false,
  placeholder = "Select or type entity type...",
}: EntityTypeComboboxProps) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value || '');

  // Fetch entity type suggestions
  const { data, isLoading } = useEntityTypes({
    platformId,
    entityClass,
    enabled: open, // Only fetch when dropdown is open
  });

  useEffect(() => {
    setInputValue(value || '');
  }, [value]);

  const handleSelect = (selectedValue: string) => {
    onChange(selectedValue);
    setInputValue(selectedValue);
    setOpen(false);
  };

  const handleInputChange = (newValue: string) => {
    setInputValue(newValue);
    // Convert to lowercase and replace spaces with underscores
    const formattedValue = newValue.toLowerCase().replace(/\s+/g, '_');
    onChange(formattedValue);
  };

  const suggestions = (data as EntityTypesResponse)?.suggestions || [];
  
  // Separate predefined and custom suggestions
  const predefinedSuggestions = suggestions.filter(s => s.is_predefined);
  const customSuggestions = suggestions.filter(s => !s.is_predefined && s.count > 0);

  // Check if current input matches any existing suggestion
  const matchesSuggestion = suggestions.some(
    s => s.entity_type === inputValue.toLowerCase().replace(/\s+/g, '_')
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          {inputValue ? getEntityTypeLabel(inputValue) : placeholder}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full p-0" align="start">
        <Command>
          <CommandInput
            placeholder="Search or create new type..."
            value={inputValue}
            onValueChange={handleInputChange}
            disabled={disabled}
          />
          <CommandList>
            {isLoading ? (
              <CommandEmpty>Loading suggestions...</CommandEmpty>
            ) : (
              <>
                {inputValue && !matchesSuggestion && (
                  <CommandGroup heading="Create New">
                    <CommandItem
                      value={inputValue}
                      onSelect={() => handleSelect(inputValue.toLowerCase().replace(/\s+/g, '_'))}
                    >
                      <span className="font-medium">
                        Create "{getEntityTypeLabel(inputValue.toLowerCase().replace(/\s+/g, '_'))}"
                      </span>
                      <Badge variant="secondary" className="ml-auto">
                        New
                      </Badge>
                    </CommandItem>
                  </CommandGroup>
                )}

                {customSuggestions.length > 0 && (
                  <CommandGroup heading="Recently Used">
                    {customSuggestions.map((suggestion) => (
                      <CommandItem
                        key={suggestion.entity_type}
                        value={suggestion.entity_type}
                        onSelect={() => handleSelect(suggestion.entity_type)}
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4',
                            value === suggestion.entity_type
                              ? 'opacity-100'
                              : 'opacity-0'
                          )}
                        />
                        {getEntityTypeLabel(suggestion.entity_type)}
                        <span className="ml-auto text-xs text-muted-foreground">
                          Used {suggestion.count} time{suggestion.count !== 1 ? 's' : ''}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}

                {predefinedSuggestions.length > 0 && (
                  <CommandGroup heading="Common Types">
                    {predefinedSuggestions.map((suggestion) => (
                      <CommandItem
                        key={suggestion.entity_type}
                        value={suggestion.entity_type}
                        onSelect={() => handleSelect(suggestion.entity_type)}
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4',
                            value === suggestion.entity_type
                              ? 'opacity-100'
                              : 'opacity-0'
                          )}
                        />
                        {getEntityTypeLabel(suggestion.entity_type)}
                        {suggestion.count > 0 && (
                          <span className="ml-auto text-xs text-muted-foreground">
                            Used {suggestion.count} time{suggestion.count !== 1 ? 's' : ''}
                          </span>
                        )}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}

                {suggestions.length === 0 && !inputValue && (
                  <CommandEmpty>No suggestions available.</CommandEmpty>
                )}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}