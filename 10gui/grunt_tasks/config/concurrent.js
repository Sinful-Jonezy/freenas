// CONCURRENT
// This allows Grunt to maintain several tasks at the same time. It's useful
// in conjunction with watch, and also for performing non-blocking build
// operations concurrently.

"use strict";

module.exports = function( grunt ) {
  var serverCommon = [
      "watch:app"
    , "watch:less"
    , "watch:images"
  ];
  this.options = {
      logConcurrentOutput : true
  };

  // Initial build of app
  this.buildWorld = [
      "browserify"
    , "copy"
    , "less"
  ];

  this.watchLocalServer   = serverCommon.concat( "watch:localServer" );
  this.watchRemoteFreeNAS = serverCommon.concat( "watch:freenasServer" );
};