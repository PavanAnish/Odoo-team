import { crud } from '../shared/store.js';

export function taxesView() {
  return crud('taxes');
}
