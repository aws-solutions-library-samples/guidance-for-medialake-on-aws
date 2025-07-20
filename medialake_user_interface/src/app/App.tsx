import { SnackbarProvider } from "notistack";

function App() {
  return (
    <SnackbarProvider
      maxSnack={3}
      anchorOrigin={{ vertical: "top", horizontal: "right" }}
    >
      {/* Existing app content */}
    </SnackbarProvider>
  );
}

export default App;
