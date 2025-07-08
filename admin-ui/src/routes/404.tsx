import { NotFoundRoute } from "@tanstack/react-router";
import { Route as rootRoute } from "./__root";

export const notFoundRoute = new NotFoundRoute({
  getParentRoute: () => rootRoute,
  component: () => {
    return (
      <div>
        <h1>404 - Not Found</h1>
        <p>The page you are looking for does not exist.</p>
      </div>
    );
  },
});
