# Custom Combobox Implementation Test Guide

## What We Built
A custom combobox component that:
- Uses UInput as the base
- Shows suggestions in a dropdown
- Allows creating new values
- Integrates directly with Pinia store
- Handles keyboard navigation
- Prevents blur issues with mousedown events

## Key Features Implemented

### 1. Direct Store Integration
- Component reads/writes directly to `permissionsStore.formState`
- No props/emits for value management
- Reactive synchronization

### 2. Input Management
- Separate tracking of display value (`inputValue`) and store value
- Formatting on blur/create (lowercase, underscores)
- Preserves user input while typing

### 3. Keyboard Navigation
- **Arrow Down**: Navigate down through suggestions
- **Arrow Up**: Navigate up through suggestions  
- **Enter**: Select highlighted item or create new
- **Escape**: Close dropdown and reset input
- **Tab**: Accept current value and move to next field

### 4. Mouse Interaction
- Click to select from suggestions
- `@mousedown.prevent` prevents blur conflicts
- Hover highlights items
- 200ms delay on blur for click handling

### 5. Filtering & Suggestions
- Shows existing custom permissions (with check icon)
- Shows common suggestions (with lightbulb icon)
- Filters as user types
- Hides already-used values

### 6. Create New Items
- Shows "Create" option for non-matching input
- Formats value before creation
- Adds to store immediately
- Item becomes available in dropdown

### 7. Accessibility
- Proper ARIA attributes for combobox
- Keyboard navigation support
- Role and state announcements

## Test Scenarios

### Test 1: Basic Selection
1. Click on Resource field
2. Dropdown should show existing resources and suggestions
3. Click on an item
4. Value should be set and dropdown closed
5. Validation should clear

### Test 2: Keyboard Navigation
1. Focus Resource field
2. Press Arrow Down to open dropdown
3. Use arrows to navigate
4. Press Enter to select
5. Value should be set

### Test 3: Creating New Value
1. Type "invoice" in Resource field
2. "Create 'invoice'" option should appear
3. Press Enter or click the create option
4. Value should be formatted and set
5. Blur the field - value should persist

### Test 4: Tab Behavior
1. Type a new value
2. Press Tab
3. Value should be created and formatted
4. Focus should move to next field

### Test 5: Escape Behavior
1. Type something in the field
2. Press Escape
3. Dropdown closes, input resets to store value

### Test 6: Filter Behavior
1. Type "rep" in Resource field
2. Should show only items containing "rep"
3. Create option for "rep" if it doesn't exist

## Console Logs to Verify
```
[FieldCombobox resource] Selecting item: {label: "report", value: "report"}
[FieldCombobox resource] Setting store value: report

[FieldCombobox resource] Creating item: invoice
[PermissionsStore] Adding temporary permission: {...}
[FieldCombobox resource] Setting store value: invoice
[FieldCombobox resource] Created and set value: invoice
```

## Advantages Over Previous Attempts
1. **No component fighting** - we control all behavior
2. **Predictable blur handling** - mousedown prevents early blur
3. **Store-first design** - all state flows through Pinia
4. **Better UX** - smooth keyboard navigation, clear visual feedback
5. **Validation works** - immediate store updates trigger validation

## Potential Improvements
- Add loading state for async suggestions
- Implement fuzzy matching for better search
- Add max height scrolling for long lists
- Consider virtual scrolling for performance