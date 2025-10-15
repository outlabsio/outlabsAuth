import { z } from "zod";

// T-Key Convention Regex Patterns
const LOWERCASE_SLUG_ALPHA = /^[a-z]+$/;
const CAMEL_CASE_VALUE = /^[a-z]+(?:[A-Z0-9][a-z0-9]*)*$/;
const LOWERCASE_SLUG_ALPHA_NUM_UNDERSCORE = /^[a-z0-9_]+$/;
const SNAKE_CASE_PROPERTY = /^[a-z_]+$/;

// Specific T-Key patterns based on conventions
const TKEY_PATTERNS = {
  // Trigram-specific patterns
  trigram_name: /^trigram:[a-z]+:name$/,
  trigram_attribute: /^trigram:attribute:[a-z]+(?:[A-Z0-9][a-z0-9]*)*:name$/,
  trigram_image: /^trigram:image:[a-z]+(?:[A-Z0-9][a-z0-9]*)*:name$/,

  // General entity patterns
  familyMember: /^familyMember:[a-z]+(?:[A-Z0-9][a-z0-9]*)*:name$/,
  element: /^element:[a-z]+:name$/,
  direction: /^direction:[a-z]+(?:[A-Z0-9][a-z0-9]*)*:name$/,
  bodyPart: /^bodyPart:[a-z]+:name$/,
  season: /^season:[a-z]+(?:[A-Z0-9][a-z0-9]*)*:(?:name|description)$/,

  // Interpretation pattern
  interpretation: /^interpretation:[a-z0-9_]+:[a-z]+:[a-z0-9_]+:[a-z_]+$/,

  // Hexagram patterns
  hexagram_basic: /^hexagram:[a-z0-9_]+:[a-z_]+$/,
  hexagram_line: /^hexagram:[a-z0-9_]+:line:[a-z0-9_]+:[a-z_]+$/,
};

// Legacy basic format validation (for backwards compatibility)
const KEY_FORMAT_REGEX = /^[a-z0-9_]+:[a-z0-9_]+:[a-z0-9_]+$/;

// Simplified schema with flexible part validation
const keySchema = z.string().refine((val) => KEY_FORMAT_REGEX.test(val), {
  message: "Key must be in format: category:identifier:property, using only lowercase letters, numbers, and underscores",
});

// List of suggested values (for autocomplete/suggestions only)
const SUGGESTED_CATEGORIES = ["trigram", "hexagram", "line", "family"] as const;
const SUGGESTED_IDENTIFIERS = ["heaven", "lake", "fire", "thunder", "wind", "water", "mountain", "earth", "middle_son", "eldest_son", "youngest_son"] as const;
const SUGGESTED_PROPERTIES = ["name", "attribute", "image", "element", "direction", "season", "family", "body_part"] as const;

// Type for a parsed key
interface KeyParts {
  category: string;
  identifier: string;
  property: string;
}

interface KeyValidationResult {
  isValid: boolean;
  error?: string;
  suggestions?: string[];
}

interface KeyStructure {
  entityType: string;
  entityId: string;
  subEntityType?: string;
  subEntityId?: string;
  fieldName: string;
}

interface KeySuggestion {
  key: string;
  description: string;
  example: string;
}

export const useKeyValidation = () => {
  // Valid entity types and their common field names
  const entityTypes = {
    hexagram: {
      fields: ["name", "description", "judgment", "image"],
      subEntities: ["line"],
      description: "I Ching hexagrams (1-64)",
    },
    trigram: {
      fields: ["name", "attribute", "image", "family", "element", "direction", "season", "body_part"],
      description: "I Ching trigrams (8 total)",
    },
    interpretation: {
      fields: ["text"],
      description: "Text interpretations by authors",
    },
    author: {
      fields: ["bio", "name"],
      description: "Author information",
    },
    element: {
      fields: ["name", "nature", "direction", "color", "shape"],
      description: "Five elements",
    },
    line_position: {
      fields: ["meaning", "sphere", "guidance", "description"],
      subEntities: ["characteristic"],
      description: "Line positions (1-6)",
    },
    season: {
      fields: ["name", "description"],
      description: "Four seasons",
    },
    color: {
      fields: ["name"],
      description: "Color names",
    },
    direction: {
      fields: ["name"],
      description: "Directional names",
    },
    shape: {
      fields: ["name"],
      description: "Shape names",
    },
    familyMember: {
      fields: ["name"],
      description: "Family member titles",
    },
    bodyPart: {
      fields: ["name"],
      description: "Body part names",
    },
  };

  /**
   * Validates a translation key format according to T-Key conventions
   */
  const validateKey = (key: string): KeyValidationResult => {
    if (!key || typeof key !== "string") {
      return {
        isValid: false,
        error: "Key is required and must be a string",
      };
    }

    // Remove any extra whitespace
    key = key.trim();

    if (key.length === 0) {
      return {
        isValid: false,
        error: "Key cannot be empty",
      };
    }

    // Split the key into parts
    const parts = key.split(":");

    if (parts.length < 2) {
      return {
        isValid: false,
        error: "Key must have at least 2 parts separated by colons (entity_type:entity_id)",
        suggestions: ["hexagram:1:name", "trigram:heaven:name", "author:wilhelm_richard:bio"],
      };
    }

    if (parts.length > 5) {
      return {
        isValid: false,
        error: "Key has too many parts (maximum 5)",
      };
    }

    // Validate specific T-Key patterns
    const entityType = parts[0]?.toLowerCase();

    // Check for specific trigram patterns first
    if (entityType === "trigram") {
      if (parts.length === 3 && parts[2] === "name") {
        // trigram:<identifier>:name pattern
        if (!TKEY_PATTERNS.trigram_name.test(key)) {
          return {
            isValid: false,
            error: "Trigram name key must follow pattern: trigram:<lowercase_identifier>:name",
            suggestions: ["trigram:heaven:name", "trigram:lake:name"],
          };
        }
      } else if (parts.length === 4 && parts[1] === "attribute" && parts[3] === "name") {
        // trigram:attribute:<value>:name pattern
        if (!TKEY_PATTERNS.trigram_attribute.test(key)) {
          return {
            isValid: false,
            error: "Trigram attribute key must follow pattern: trigram:attribute:<camelCaseValue>:name",
            suggestions: ["trigram:attribute:creative:name", "trigram:attribute:joyous:name"],
          };
        }
      } else if (parts.length === 4 && parts[1] === "image" && parts[3] === "name") {
        // trigram:image:<value>:name pattern
        if (!TKEY_PATTERNS.trigram_image.test(key)) {
          return {
            isValid: false,
            error: "Trigram image key must follow pattern: trigram:image:<camelCaseValue>:name",
            suggestions: ["trigram:image:sky:name", "trigram:image:marshLake:name"],
          };
        }
      } else {
        return {
          isValid: false,
          error: "Invalid trigram key pattern. Must be: trigram:<id>:name, trigram:attribute:<value>:name, or trigram:image:<value>:name",
        };
      }
    }
    // Check other entity patterns
    else if (entityType === "familymember") {
      if (!TKEY_PATTERNS.familyMember.test(key)) {
        return {
          isValid: false,
          error: "Family member key must follow pattern: familyMember:<camelCaseIdentifier>:name",
          suggestions: ["familyMember:father:name", "familyMember:youngestDaughter:name"],
        };
      }
    } else if (entityType === "element") {
      if (!TKEY_PATTERNS.element.test(key)) {
        return {
          isValid: false,
          error: "Element key must follow pattern: element:<lowercase_identifier>:name",
          suggestions: ["element:fire:name", "element:water:name"],
        };
      }
    } else if (entityType === "direction") {
      if (!TKEY_PATTERNS.direction.test(key)) {
        return {
          isValid: false,
          error: "Direction key must follow pattern: direction:<camelCaseIdentifier>:name",
          suggestions: ["direction:north:name", "direction:northWest:name"],
        };
      }
    } else if (entityType === "bodypart") {
      if (!TKEY_PATTERNS.bodyPart.test(key)) {
        return {
          isValid: false,
          error: "Body part key must follow pattern: bodyPart:<lowercase_identifier>:name",
          suggestions: ["bodyPart:head:name", "bodyPart:mouth:name"],
        };
      }
    } else if (entityType === "season") {
      if (!TKEY_PATTERNS.season.test(key)) {
        return {
          isValid: false,
          error: "Season key must follow pattern: season:<camelCaseIdentifier>:(name|description)",
          suggestions: ["season:spring:name", "season:lateAutumn:description"],
        };
      }
    } else if (entityType === "interpretation") {
      if (!TKEY_PATTERNS.interpretation.test(key)) {
        return {
          isValid: false,
          error: "Interpretation key must follow pattern: interpretation:<author_id>:<entity_type>:<entity_id>:<property>",
          suggestions: ["interpretation:wilhelm_richard:hexagram:1:judgment"],
        };
      }
    } else if (entityType === "hexagram") {
      const isBasicPattern = TKEY_PATTERNS.hexagram_basic.test(key);
      const isLinePattern = TKEY_PATTERNS.hexagram_line.test(key);

      if (!isBasicPattern && !isLinePattern) {
        return {
          isValid: false,
          error: "Hexagram key must follow pattern: hexagram:<id>:<property> or hexagram:<id>:line:<line_id>:<property>",
          suggestions: ["hexagram:1:name", "hexagram:1:line:1:meaning"],
        };
      }
    } else {
      // For unknown entity types, fall back to basic validation
      const entityConfig = entityTypes[entityType as keyof typeof entityTypes];
      if (!entityConfig) {
        const validTypes = Object.keys(entityTypes);
        return {
          isValid: false,
          error: `Unknown entity type "${entityType}"`,
          suggestions: validTypes.slice(0, 5).map((type) => `${type}:example_id:name`),
        };
      }

      // Basic validation for known entity types not covered by strict patterns
      const fieldName = parts[parts.length - 1]?.toLowerCase();
      if (!fieldName || !entityConfig.fields.includes(fieldName)) {
        return {
          isValid: false,
          error: `Invalid field "${fieldName}" for entity type "${entityType}"`,
          suggestions: entityConfig.fields.map((field) => `${entityType}:example_id:${field}`),
        };
      }
    }

    return { isValid: true };
  };

  /**
   * Parses a key into its structural components
   */
  const parseKey = (key: string): KeyStructure | null => {
    const validation = validateKey(key);
    if (!validation.isValid) {
      return null;
    }

    const parts = key.split(":");

    if (parts.length === 2) {
      const entityType = parts[0];
      const entityId = parts[1];
      if (!entityType || !entityId) return null;

      return {
        entityType,
        entityId,
        fieldName: entityId, // For simple cases like color:red
      };
    }

    if (parts.length === 3) {
      const entityType = parts[0];
      const entityId = parts[1];
      const fieldName = parts[2];
      if (!entityType || !entityId || !fieldName) return null;

      return {
        entityType,
        entityId,
        fieldName,
      };
    }

    if (parts.length === 4) {
      const entityType = parts[0];
      const entityId = parts[1];
      const subEntityType = parts[2];
      const fieldName = parts[3];
      if (!entityType || !entityId || !subEntityType || !fieldName) return null;

      return {
        entityType,
        entityId,
        subEntityType,
        fieldName,
      };
    }

    if (parts.length === 5) {
      const entityType = parts[0];
      const entityId = parts[1];
      const subEntityType = parts[2];
      const subEntityId = parts[3];
      const fieldName = parts[4];
      if (!entityType || !entityId || !subEntityType || !subEntityId || !fieldName) return null;

      return {
        entityType,
        entityId,
        subEntityType,
        subEntityId,
        fieldName,
      };
    }

    return null;
  };

  /**
   * Suggests a properly formatted key according to T-Key conventions
   */
  const suggestKey = (entityType: string, entityId: string, fieldName: string, subEntityType?: string, subEntityId?: string): string => {
    const lowerEntityType = entityType.toLowerCase();

    // Handle trigram-specific patterns
    if (lowerEntityType === "trigram") {
      if (fieldName === "name") {
        // trigram:<lowercase_identifier>:name
        return `trigram:${entityId.toLowerCase()}:name`;
      } else if (fieldName === "attribute") {
        // trigram:attribute:<camelCase_value>:name
        return `trigram:attribute:${entityId}:name`;
      } else if (fieldName === "image") {
        // trigram:image:<camelCase_value>:name
        return `trigram:image:${entityId}:name`;
      } else {
        // Default trigram pattern
        return `trigram:${entityId.toLowerCase()}:${fieldName}`;
      }
    }

    // Handle other entity types with specific casing requirements
    const entityTypeCasing = {
      familymember: "familyMember", // camelCase for identifiers
      element: "element", // lowercase for identifiers
      direction: "direction", // camelCase for identifiers
      bodypart: "bodyPart", // lowercase for identifiers
      season: "season", // camelCase for identifiers
      hexagram: "hexagram", // mixed case allowed
      interpretation: "interpretation", // snake_case for identifiers
      author: "author", // snake_case for identifiers
      line_position: "line_position", // snake_case for identifiers
      color: "color", // lowercase
      shape: "shape", // lowercase
    };

    const correctEntityType = entityTypeCasing[lowerEntityType as keyof typeof entityTypeCasing] || lowerEntityType;

    // For interpretation keys, use the 5-part format
    if (lowerEntityType === "interpretation" && subEntityType && subEntityId) {
      return `interpretation:${entityId}:${subEntityType}:${subEntityId}:${fieldName}`;
    }

    // For hexagram line keys
    if (lowerEntityType === "hexagram" && subEntityType === "line" && subEntityId) {
      return `hexagram:${entityId}:line:${subEntityId}:${fieldName}`;
    }

    // Standard 3-part format
    const parts = [correctEntityType, entityId, fieldName.toLowerCase()];
    return parts.join(":");
  };

  /**
   * Gets key suggestions for a given entity type
   */
  const getKeySuggestions = (entityType: string): KeySuggestion[] => {
    const entityConfig = entityTypes[entityType.toLowerCase() as keyof typeof entityTypes];
    if (!entityConfig) {
      return [];
    }

    const suggestions: KeySuggestion[] = [];

    entityConfig.fields.forEach((field) => {
      suggestions.push({
        key: `${entityType}:example_id:${field}`,
        description: `${entityConfig.description} - ${field}`,
        example: getExampleKey(entityType, field),
      });
    });

    return suggestions;
  };

  /**
   * Gets an example key for demonstration that follows T-Key conventions
   */
  const getExampleKey = (entityType: string, fieldName: string): string => {
    const examples: Record<string, Record<string, string>> = {
      hexagram: {
        name: "hexagram:1:name",
        description: "hexagram:1:description",
        judgment: "hexagram:1:judgment",
        image: "hexagram:1:image",
      },
      trigram: {
        name: "trigram:heaven:name",
        attribute: "trigram:attribute:creative:name",
        image: "trigram:image:sky:name",
        family: "familyMember:father:name",
        element: "element:metal:name",
        direction: "direction:northWest:name",
        body_part: "bodyPart:head:name",
      },
      author: {
        bio: "author:wilhelm_richard:bio",
        name: "author:wilhelm_richard:name",
      },
      element: {
        name: "element:fire:name",
        nature: "element:fire:nature",
      },
      line_position: {
        meaning: "line_position:1:meaning",
        sphere: "line_position:1:sphere",
      },
      season: {
        name: "season:spring:name",
        description: "season:lateAutumn:description",
      },
      familyMember: {
        name: "familyMember:father:name",
      },
      direction: {
        name: "direction:northWest:name",
      },
      bodyPart: {
        name: "bodyPart:head:name",
      },
      interpretation: {
        text: "interpretation:wilhelm_richard:hexagram:1:text",
      },
    };

    return examples[entityType]?.[fieldName] || `${entityType}:example:${fieldName}`;
  };

  /**
   * Formats a key for display with color coding or styling hints
   */
  const formatKeyForDisplay = (key: string) => {
    const parts = key.split(":");
    return {
      entityType: parts[0],
      entityId: parts[1],
      subEntityType: parts[2],
      subEntityId: parts[3],
      fieldName: parts[parts.length - 1],
      parts,
    };
  };

  /**
   * Gets field name suggestions for an entity type
   */
  const getFieldSuggestions = (entityType: string): string[] => {
    const entityConfig = entityTypes[entityType.toLowerCase() as keyof typeof entityTypes];
    return entityConfig?.fields || [];
  };

  /**
   * Validates an identifier (used in keys)
   */
  const validateIdentifier = (identifier: string): KeyValidationResult => {
    if (!identifier) {
      return {
        isValid: false,
        error: "Identifier is required",
      };
    }

    if (!/^[a-z0-9_]+$/.test(identifier)) {
      return {
        isValid: false,
        error: "Identifier must be lowercase and contain only letters, numbers, and underscores",
      };
    }

    if (identifier.startsWith("_") || identifier.endsWith("_")) {
      return {
        isValid: false,
        error: "Identifier cannot start or end with underscore",
      };
    }

    if (identifier.includes("__")) {
      return {
        isValid: false,
        error: "Identifier cannot contain consecutive underscores",
      };
    }

    return { isValid: true };
  };

  /**
   * Converts a display name to a valid identifier
   */
  const nameToIdentifier = (name: string): string => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, "") // Remove special characters
      .replace(/\s+/g, "_") // Replace spaces with underscores
      .replace(/_+/g, "_") // Replace multiple underscores with single
      .replace(/^_|_$/g, ""); // Remove leading/trailing underscores
  };

  return {
    validateKey,
    parseKey,
    suggestKey,
    getKeySuggestions,
    getExampleKey,
    formatKeyForDisplay,
    getFieldSuggestions,
    validateIdentifier,
    nameToIdentifier,
    entityTypes,
  };
};
