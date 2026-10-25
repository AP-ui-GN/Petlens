import { Text } from 'react-native';

import { connectionTitle } from '../../lib/connection-messages';
import { Note } from '../ui';
import type { ConnectionState } from '../../hooks/use-connection';

type Props = {
  state: ConnectionState;
  onRetry: () => void;
};

export function ConnectionStatus({ state, onRetry }: Props) {
  if (state.kind === 'checking') {
    return (
      <Note tone="info" title="Checking the server">
        Looking for the analysis server.
      </Note>
    );
  }

  if (state.kind === 'online') {
    return (
      <Note tone="info" title="Connected">
        The analysis server answered.
      </Note>
    );
  }

  return (
    <Note tone="error" title={state.failure === 'config' ? 'Not configured' : connectionTitle(state.failure)}>
      {state.message} Your chosen clip stays selected.
      <Text onPress={onRetry} accessibilityRole="button" style={{ fontWeight: '700' }}>
        {' '}
        Retry
      </Text>
    </Note>
  );
}
