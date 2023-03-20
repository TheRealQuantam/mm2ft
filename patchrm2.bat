@set pre=rm2
@set def_src_path=Rockman 2 - Dr. Wily no Nazo (Japan).nes

@if "%~1"=="" (set src_path="%def_src_path%") else (set src_path="%~1")
@if not exist %src_path% goto :no_file

@for %%s in (ft ftdemo) do del %pre%%%s.nes

xdelta3 -d -s %src_path% %pre%ft.xdelta %pre%ft.nes
@if errorlevel 1 @goto :failed

xdelta3 -d -s %pre%ft.nes %pre%ftdemo.xdelta %pre%ftdemo.nes
@if errorlevel 1 @goto :failed

@echo Patch successful!

@goto :done
	
:failed
@echo ERROR: Patch failed!

@goto :done
	
:no_file
@echo ERROR: %src_path% does not exist!

:done
@pause