const fs = require('fs');
const path = require('path');

describe('frontend nginx media proxy', () => {
  const conf = fs.readFileSync(path.join(__dirname, '../nginx.conf'), 'utf8');

  test('uploaded /media/ files are served from the media volume, not SPA static', () => {
    expect(conf).toMatch(/location \^~ \/media\//);
    expect(conf).toMatch(/root \/srv;/);
    expect(conf).toMatch(/open_file_cache off;/);
    expect(conf).toMatch(/location @media_django/);
    expect(conf).toMatch(/proxy_pass http:\/\/\$django_upstream/);
  });
});
