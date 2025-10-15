// Known I Ching author collaborations
const AUTHOR_COLLABORATIONS: Record<string, string[]> = {
  ritsema_rudolf: ["karcher_stephen"],
  karcher_stephen: ["ritsema_rudolf"],
  wilhelm_richard: ["baynes_cary"],
  baynes_cary: ["wilhelm_richard"],
};

export const useCollaboration = () => {
  // Get list of collaboration partners for an author
  const getCollaborationAuthors = (authorIdentifier: string): string[] => {
    return AUTHOR_COLLABORATIONS[authorIdentifier] || [];
  };

  // Check if an author has collaborations
  const hasCollaborations = (authorIdentifier: string): boolean => {
    return getCollaborationAuthors(authorIdentifier).length > 0;
  };

  // Format author identifier to display name
  const formatAuthorName = (identifier: string): string => {
    return identifier
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Get the primary author identifier for collaborations
  const getPrimaryAuthorForCollaborations = (authorIdentifier: string): string => {
    const collaborationPrimaryMap: Record<string, string> = {
      karcher_stephen: "ritsema_rudolf", // Karcher's work is under Ritsema
      baynes_cary: "wilhelm_richard", // Baynes's work is under Wilhelm
    };

    return collaborationPrimaryMap[authorIdentifier] || authorIdentifier;
  };

  // Check if an author is a secondary collaborator (their works are stored under another author)
  const isSecondaryCollaborator = (authorIdentifier: string): boolean => {
    return getPrimaryAuthorForCollaborations(authorIdentifier) !== authorIdentifier;
  };

  // Get collaboration summary for display
  const getCollaborationSummary = (authorIdentifier: string): string => {
    const collaborators = getCollaborationAuthors(authorIdentifier);
    if (collaborators.length === 0) return "";

    if (collaborators.length === 1 && collaborators[0]) {
      return `Collaborated with ${formatAuthorName(collaborators[0])}`;
    }

    return `Collaborated with ${collaborators.length} authors`;
  };

  // Get formatted collaboration partner names
  const getFormattedCollaborators = (authorIdentifier: string): string[] => {
    const collaborators = getCollaborationAuthors(authorIdentifier);
    return collaborators.map(formatAuthorName);
  };

  // Get collaboration status and details
  const getCollaborationDetails = (authorIdentifier: string) => {
    const collaborators = getCollaborationAuthors(authorIdentifier);
    const isSecondary = isSecondaryCollaborator(authorIdentifier);
    const primaryAuthor = getPrimaryAuthorForCollaborations(authorIdentifier);

    return {
      hasCollaborations: collaborators.length > 0,
      collaborators,
      formattedCollaborators: getFormattedCollaborators(authorIdentifier),
      isSecondaryCollaborator: isSecondary,
      primaryAuthor,
      primaryAuthorName: formatAuthorName(primaryAuthor),
      summary: getCollaborationSummary(authorIdentifier),
    };
  };

  return {
    getCollaborationAuthors,
    hasCollaborations,
    formatAuthorName,
    getPrimaryAuthorForCollaborations,
    isSecondaryCollaborator,
    getCollaborationSummary,
    getFormattedCollaborators,
    getCollaborationDetails,
  };
};
