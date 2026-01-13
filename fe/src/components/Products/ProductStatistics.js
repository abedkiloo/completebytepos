import React from 'react';
import { formatCompactNumber, formatCompactCurrency } from '../../utils/formatters';
import './Products.css';

const ProductStatistics = ({ statistics }) => {
  if (!statistics) return null;

  return (
    <div className="product-statistics">
      <div className="stat-card">
        <h3>Total Products</h3>
        <p className="stat-value">{formatCompactNumber(statistics.total_products)}</p>
      </div>
      <div className="stat-card">
        <h3>Active Products</h3>
        <p className="stat-value">{formatCompactNumber(statistics.active_products)}</p>
      </div>
      <div className="stat-card warning">
        <h3>Low Stock</h3>
        <p className="stat-value">{formatCompactNumber(statistics.low_stock_products)}</p>
      </div>
      <div className="stat-card danger">
        <h3>Out of Stock</h3>
        <p className="stat-value">{formatCompactNumber(statistics.out_of_stock_products)}</p>
      </div>
      <div className="stat-card success">
        <h3>Inventory Value</h3>
        <p className="stat-value">{formatCompactCurrency(statistics.total_inventory_value)}</p>
      </div>
      <div className="stat-card success">
        <h3>Products Value</h3>
        <p className="stat-value">{formatCompactCurrency(statistics.total_products_value)}</p>
      </div>
    </div>
  );
};

export default ProductStatistics;

