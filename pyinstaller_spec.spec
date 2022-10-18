# -*- mode: python -*-

block_cipher = None

added_files = [
         ( 'estimator/interface/*.glade', 'estimator/interface' ),
         ( 'estimator/interface/*.png', 'estimator/interface' ),
         ( 'estimator/interface/*.svg', 'estimator/interface' ),
         ( 'estimator/database/*.eproj', 'estimator/database' ),
		 ( 'estimator/meas_templates/*.py', 'estimator/meas_templates' )
		 ]

a = Analysis(['gestimator.py'],
             pathex=['C:\\Users\\User\\Desktop\\GEstimator'],
             binaries=None,
             datas=added_files,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='GEstimator',
          debug=False,
          strip=False,
          upx=False,
          console=False,
          icon = 'GEstimator.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               name='ApplicationFiles')
