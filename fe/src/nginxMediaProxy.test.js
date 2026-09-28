const fs = require('fs');
const path = require('path');

describe('frontend nginx media proxy', () => {
  const conf = fs.readFileSync(path.join(__dirname, '../nginx.conf'), 'utf8');

  test('uploaded /media/ files are not captured by the static-asset regex', () => {
    expect(conf).toMatch(/location \^~ \/media\//);
    expect(conf).toMatch(/proxy_pass http:\/\/\$django_upstream/);
  });
});
