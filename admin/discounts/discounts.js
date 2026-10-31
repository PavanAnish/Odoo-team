import { crud } from '../shared/store.js';

export function discountsView() {
  return crud('discounts');
}
