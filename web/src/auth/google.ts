import { auth } from '../api/client';
import { useStore } from '../state/store';
import { toast } from '../components/Toast';

let googleInitialized = false;

/**
 * Initialize Google Identity Services
 */
export async function initGoogleSignIn(): Promise<void> {
  if (googleInitialized) return;

  const store = useStore.getState();

  // Get client ID from server
  const clientId = await auth.getClientId();
  if (!clientId) {
    console.log('No Google Client ID - running in development mode');
    return;
  }

  store.setGoogleClientId(clientId);

  // Wait for Google script to load
  await waitForGoogleScript();

  // Initialize Google Identity Services
  google.accounts.id.initialize({
    client_id: clientId,
    callback: handleGoogleCredential,
    auto_select: false,
  });

  googleInitialized = true;
}

/**
 * Render Google Sign-In button
 */
export function renderGoogleButton(container: HTMLElement): void {
  const clientId = useStore.getState().googleClientId;
  if (!clientId || !googleInitialized) {
    console.log('Google Sign-In not available');
    return;
  }

  google.accounts.id.renderButton(container, {
    theme: 'filled_black',
    size: 'large',
    text: 'signin_with',
    shape: 'rectangular',
    width: 280,
  });
}

/**
 * Handle Google credential response
 */
async function handleGoogleCredential(
  response: google.accounts.id.CredentialResponse
): Promise<void> {
  const store = useStore.getState();

  try {
    const authResponse = await auth.googleLogin(response.credential);
    store.setToken(authResponse.token);
    store.setUser(authResponse.user);

    // Trigger app reload/init
    window.dispatchEvent(new CustomEvent('auth:login'));
  } catch (error) {
    console.error('Google login failed:', error);
    toast.error('Login failed. Please try again.');
    window.dispatchEvent(
      new CustomEvent('auth:error', { detail: { error } })
    );
  }
}

/**
 * Check authentication status
 */
export async function checkAuth(): Promise<boolean> {
  const store = useStore.getState();

  try {
    const user = await auth.me();
    store.setUser(user);
    return true;
  } catch {
    // Auth failed - clear any stale token
    if (store.token) {
      store.logout();
    }
    return false;
  }
}

/**
 * Logout user
 */
export function logout(): void {
  const store = useStore.getState();
  store.logout();

  // TODO: Remove legacy token handling after existing JWTs expire (they have 7 day expiry)
  // Clear any legacy token storage from old app.js
  localStorage.removeItem('token');

  // Disable Google auto-select on next visit
  if (googleInitialized) {
    google.accounts.id.disableAutoSelect();
  }

  // Trigger UI update
  window.dispatchEvent(new CustomEvent('auth:logout'));
}

/**
 * Wait for Google script to load
 */
function waitForGoogleScript(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof google !== 'undefined' && google.accounts) {
      resolve();
      return;
    }

    // Poll for Google script
    const checkGoogle = () => {
      if (typeof google !== 'undefined' && google.accounts) {
        resolve();
      } else {
        setTimeout(checkGoogle, 100);
      }
    };
    checkGoogle();
  });
}