import { crud } from '../shared/store.js';

export function productsView() {
  return crud('products');
}
